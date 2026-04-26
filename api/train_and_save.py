"""
E-Mall SASRec — Training & Checkpoint Script
==============================================
Run this ONCE to train the SASRec model and save:
  1. Model weights  -> api/checkpoints/sasrec_emall.pth
  2. Item mappings  -> api/checkpoints/sasrec_emall.pth (embedded)

This script applies the critical fixes identified in the analysis:
  [OK] BCEWithLogitsLoss(reduction='none') for correct masked loss
  [OK] Vectorised groupby() instead of iterrows()
  [OK] Sorted item IDs for deterministic mapping
  [OK] Filtered to purchase + add_to_cart interactions (stronger signal)
  [OK] HIDDEN_DIM=64 for more capacity
  [OK] Early stopping with patience=20
  [OK] Gradient clipping

Usage:
    cd "GP - Dataset"
    python api/train_and_save.py
"""

import os
import sys
import random
import math
import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from collections import defaultdict

# Add api/ to path so we can import model
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import SASRec
from config import (
    DATA_DIR, API_DIR, MODEL_CHECKPOINT_PATH,
    MAX_SEQ_LEN, HIDDEN_DIM, NUM_BLOCKS, NUM_HEADS, DROPOUT_RATE,
)


def set_seed(seed: int = 42):
    """Ensure full reproducibility across runs."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


class SASRecDataset(Dataset):
    """PyTorch Dataset for SASRec training with negative sampling."""

    def __init__(self, user_seqs: dict, max_len: int, num_items: int):
        self.user_seqs = user_seqs
        self.max_len = max_len
        self.num_items = num_items
        self.users = list(user_seqs.keys())

    def __len__(self) -> int:
        return len(self.users)

    def __getitem__(self, idx: int):
        user = self.users[idx]
        seq = self.user_seqs[user]

        # Input -> all but last; Labels -> all but first (shifted by 1)
        tokens = seq[:-1]
        labels = seq[1:]

        # Truncate to max_len (keep most recent)
        tokens = tokens[-self.max_len:]
        labels = labels[-self.max_len:]

        # Left-pad with 0
        pad_len = self.max_len - len(tokens)
        tokens = [0] * pad_len + tokens
        labels = [0] * pad_len + labels

        # Negative sampling (one per positive, skip padding)
        user_set = set(seq)
        neg_labels = []
        for lbl in labels:
            if lbl == 0:
                neg_labels.append(0)
            else:
                neg = random.randint(1, self.num_items - 1)
                while neg in user_set:
                    neg = random.randint(1, self.num_items - 1)
                neg_labels.append(neg)

        return (
            torch.LongTensor(tokens),
            torch.LongTensor(labels),
            torch.LongTensor(neg_labels),
        )


def dedup_consecutive(seq: list) -> list:
    """Remove consecutive duplicates from a sequence."""
    if not seq:
        return seq
    return [seq[i] for i in range(len(seq)) if i == 0 or seq[i] != seq[i - 1]]


def evaluate(model, dataset_dict, train_dict, item_num, device, K=10):
    """Evaluate HR@K and NDCG@K using 99-negative sampling."""
    model.eval()
    NDCG, HT, valid_users = 0.0, 0.0, 0.0

    with torch.no_grad():
        for u in dataset_dict:
            if len(train_dict.get(u, [])) < 1 or len(dataset_dict.get(u, [])) < 1:
                continue

            seq = train_dict[u][-MAX_SEQ_LEN:]
            padded = [0] * (MAX_SEQ_LEN - len(seq)) + seq
            target = dataset_dict[u][0]

            # 99 negatives
            negs = []
            user_set = set(train_dict[u])
            while len(negs) < 99:
                neg = random.randint(1, item_num - 1)
                if neg not in user_set and neg != target:
                    negs.append(neg)

            items = [target] + negs
            seq_t = torch.LongTensor([padded]).to(device)
            item_t = torch.LongTensor([items]).to(device)
            preds = model.predict(seq_t, item_t)[0]

            rank = (preds > preds[0]).sum().item() + 1
            if rank <= K:
                HT += 1
                NDCG += 1 / math.log2(rank + 1)
            valid_users += 1

    return HT / max(valid_users, 1), NDCG / max(valid_users, 1)


def main():
    set_seed(42)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"{'=' * 60}")
    print(f"  E-Mall SASRec - Training Pipeline")
    print(f"  Device: {device}")
    print(f"{'=' * 60}\n")

    # ── 1. Load Data ────────────────────────────────────────────
    print("[1/5] Loading interactions...")
    t0 = time.time()
    interactions_df = pd.read_csv(os.path.join(DATA_DIR, "interactions.csv"))
    interactions_df["timestamp"] = pd.to_datetime(interactions_df["timestamp"])
    interactions_df = interactions_df.sort_values(by=["user_id", "timestamp"])

    # FIX: Filter to strong signals only (purchase + add_to_cart)
    strong_df = interactions_df[
        interactions_df["interaction_type"].isin(["purchase", "add_to_cart"])
    ].copy()
    print(f"   Total interactions: {len(interactions_df):,}")
    print(f"   Strong signals (purchase + add_to_cart): {len(strong_df):,}")

    # ── 2. Build Mappings ───────────────────────────────────────
    print("[2/5] Building item mappings...")

    # FIX: Sort IDs for deterministic mapping
    item_ids = sorted(strong_df["product_id"].unique())
    item2idx = {pid: idx for idx, pid in enumerate(item_ids, start=1)}
    idx2item = {idx: pid for pid, idx in item2idx.items()}
    NUM_ITEMS = len(item2idx) + 1  # +1 for padding index 0

    print(f"   Unique items: {NUM_ITEMS - 1}")

    # ── 3. Build Sequences ──────────────────────────────────────
    print("[3/5] Building user sequences...")

    # FIX: Vectorised groupby instead of iterrows
    strong_df["item_idx"] = strong_df["product_id"].map(item2idx)
    user_sequences = strong_df.groupby("user_id")["item_idx"].apply(list).to_dict()

    # Deduplicate consecutive items
    user_sequences = {u: dedup_consecutive(s) for u, s in user_sequences.items()}

    # Remove users with < 3 items (needed for train/val/test split)
    user_sequences = {u: s for u, s in user_sequences.items() if len(s) >= 3}
    print(f"   Valid users (>=3 items): {len(user_sequences):,}")

    # Leave-one-out split
    train_data, val_data, test_data = {}, {}, {}
    for user, seq in user_sequences.items():
        train_data[user] = seq[:-2]
        val_data[user] = [seq[-2]]
        test_data[user] = [seq[-1]]

    # ── 4. Train ────────────────────────────────────────────────
    print("[4/5] Training SASRec model...")
    print(f"   Hyperparameters:")
    print(f"     HIDDEN_DIM  = {HIDDEN_DIM}")
    print(f"     MAX_SEQ_LEN = {MAX_SEQ_LEN}")
    print(f"     NUM_BLOCKS  = {NUM_BLOCKS}")
    print(f"     NUM_HEADS   = {NUM_HEADS}")
    print(f"     DROPOUT     = {DROPOUT_RATE}")

    train_dataset = SASRecDataset(train_data, MAX_SEQ_LEN, NUM_ITEMS)
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True, num_workers=0)

    model = SASRec(
        num_items=NUM_ITEMS,
        max_len=MAX_SEQ_LEN,
        hidden_dim=HIDDEN_DIM,
        num_blocks=NUM_BLOCKS,
        num_heads=NUM_HEADS,
        dropout_rate=DROPOUT_RATE,
    ).to(device)

    optimizer = optim.Adam(model.parameters(), lr=0.001, betas=(0.9, 0.98))

    # FIX: reduction='none' so per-element masking works
    bce_criterion = nn.BCEWithLogitsLoss(reduction="none")

    EPOCHS = 200
    PATIENCE = 20
    best_ndcg = 0.0
    best_state = None
    patience_count = 0

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0

        for batch_seq, batch_pos, batch_neg in train_loader:
            batch_seq = batch_seq.to(device)
            batch_pos = batch_pos.to(device)
            batch_neg = batch_neg.to(device)

            optimizer.zero_grad()

            seq_emb = model(batch_seq)
            pos_emb = model.item_emb(batch_pos)
            neg_emb = model.item_emb(batch_neg)

            pos_logits = (seq_emb * pos_emb).sum(dim=-1)
            neg_logits = (seq_emb * neg_emb).sum(dim=-1)

            istarget = (batch_pos > 0).float()

            pos_loss = bce_criterion(pos_logits, torch.ones_like(pos_logits))
            neg_loss = bce_criterion(neg_logits, torch.zeros_like(neg_logits))

            loss = ((pos_loss + neg_loss) * istarget).sum() / istarget.sum()
            loss.backward()

            # Gradient clipping for stability
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)

            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)

        # Evaluate every 5 epochs
        if epoch % 5 == 0 or epoch == 1:
            val_hr, val_ndcg = evaluate(model, val_data, train_data, NUM_ITEMS, device)
            print(f"   Epoch {epoch:3d}/{EPOCHS} - Loss: {avg_loss:.4f} | Val HR@10: {val_hr:.4f} | Val NDCG@10: {val_ndcg:.4f}")

            if val_ndcg > best_ndcg:
                best_ndcg = val_ndcg
                best_state = model.state_dict().copy()
                patience_count = 0
                print(f"   >> New best NDCG@10: {best_ndcg:.4f}")
            else:
                patience_count += 5
                if patience_count >= PATIENCE:
                    print(f"   [STOP] Early stopping at epoch {epoch} (patience={PATIENCE})")
                    break
        else:
            if epoch <= 10 or epoch % 10 == 0:
                print(f"   Epoch {epoch:3d}/{EPOCHS} - Loss: {avg_loss:.4f}")

    # Load best model
    if best_state is not None:
        model.load_state_dict(best_state)

    # Final test evaluation
    train_and_val = {u: train_data[u] + val_data.get(u, []) for u in train_data}
    test_hr, test_ndcg = evaluate(model, test_data, train_and_val, NUM_ITEMS, device)
    print(f"\n   [DONE] Final Test HR@10: {test_hr:.4f} | Test NDCG@10: {test_ndcg:.4f}")

    # ── 5. Save Checkpoint ──────────────────────────────────────
    print("\n[5/5] Saving checkpoint...")
    os.makedirs(os.path.dirname(MODEL_CHECKPOINT_PATH), exist_ok=True)

    # Also build the full user_sequences from ALL interactions for inference
    # (so the API can filter out previously seen items)
    interactions_df["item_idx"] = interactions_df["product_id"].map(
        lambda x: item2idx.get(x, 0)
    )
    full_user_sequences = (
        interactions_df[interactions_df["item_idx"] > 0]
        .groupby("user_id")["item_idx"]
        .apply(list)
        .to_dict()
    )

    # Load product metadata for enriched responses
    products_df = pd.read_csv(os.path.join(DATA_DIR, "products.csv"))
    product_meta = {}
    for _, row in products_df.iterrows():
        pid = row["product_id"]
        if pid in item2idx:
            product_meta[pid] = {
                "product_name": row["product_name"],
                "category": row["category"],
                "price": float(row["price"]),
                "image_url": row["image_url"],
            }

    checkpoint = {
        "model_state_dict": model.state_dict(),
        "item2idx": item2idx,
        "idx2item": idx2item,
        "user_sequences": full_user_sequences,
        "product_meta": product_meta,
        "hyperparams": {
            "num_items": NUM_ITEMS,
            "max_len": MAX_SEQ_LEN,
            "hidden_dim": HIDDEN_DIM,
            "num_blocks": NUM_BLOCKS,
            "num_heads": NUM_HEADS,
            "dropout_rate": DROPOUT_RATE,
        },
        "metrics": {
            "test_hr_at_10": test_hr,
            "test_ndcg_at_10": test_ndcg,
            "best_val_ndcg_at_10": best_ndcg,
        },
    }

    torch.save(checkpoint, MODEL_CHECKPOINT_PATH)
    file_size_mb = os.path.getsize(MODEL_CHECKPOINT_PATH) / (1024 * 1024)
    print(f"   [SAVED] {MODEL_CHECKPOINT_PATH}")
    print(f"   Checkpoint size: {file_size_mb:.1f} MB")
    print(f"\n   Total training time: {time.time() - t0:.1f}s")
    print(f"\n{'=' * 60}")
    print(f"  Training complete! You can now start the API server:")
    print(f"  cd \"GP - Dataset\" && uvicorn api.main:app --reload --port 8000")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
