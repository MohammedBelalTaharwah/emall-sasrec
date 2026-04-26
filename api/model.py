"""
E-Mall SASRec — Model Architecture
====================================
Clean, modular SASRec (Self-Attentive Sequential Recommendation) model.
This file defines the exact same architecture used during training,
so that saved weights can be loaded correctly at inference time.

Reference: Kang & McAuley, "Self-Attentive Sequential Recommendation" (2018)
"""

import torch
import torch.nn as nn


class PointWiseFeedForward(nn.Module):
    """Position-wise Feed-Forward Network using Conv1d (kernel=1)."""

    def __init__(self, hidden_dim: int, dropout_rate: float):
        super().__init__()
        self.conv1 = nn.Conv1d(hidden_dim, hidden_dim, kernel_size=1)
        self.dropout1 = nn.Dropout(p=dropout_rate)
        self.relu = nn.ReLU()
        self.conv2 = nn.Conv1d(hidden_dim, hidden_dim, kernel_size=1)
        self.dropout2 = nn.Dropout(p=dropout_rate)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        # inputs: (batch, seq_len, hidden_dim)
        outputs = inputs.transpose(-1, -2)  # (batch, hidden_dim, seq_len)
        outputs = self.dropout1(self.relu(self.conv1(outputs)))
        outputs = self.dropout2(self.conv2(outputs))
        outputs = outputs.transpose(-1, -2)  # (batch, seq_len, hidden_dim)
        return outputs


class SASRecBlock(nn.Module):
    """Single Transformer block: Self-Attention + FFN with LayerNorm & residual."""

    def __init__(self, hidden_dim: int, num_heads: int, dropout_rate: float):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            hidden_dim, num_heads, dropout=dropout_rate, batch_first=True
        )
        self.ffn = PointWiseFeedForward(hidden_dim, dropout_rate)
        self.norm1 = nn.LayerNorm(hidden_dim, eps=1e-8)
        self.norm2 = nn.LayerNorm(hidden_dim, eps=1e-8)
        self.dropout = nn.Dropout(p=dropout_rate)

    def forward(self, inputs: torch.Tensor, attn_mask: torch.Tensor) -> torch.Tensor:
        # Self-Attention with pre-norm
        normed_inputs = self.norm1(inputs)
        attn_out, _ = self.attn(normed_inputs, normed_inputs, normed_inputs, attn_mask=attn_mask)
        inputs = inputs + self.dropout(attn_out)

        # FFN with pre-norm
        normed_inputs2 = self.norm2(inputs)
        ffn_out = self.ffn(normed_inputs2)
        inputs = inputs + self.dropout(ffn_out)
        return inputs


class SASRec(nn.Module):
    """
    Self-Attentive Sequential Recommendation model.

    Args:
        num_items:    Total number of items (including padding at index 0).
        max_len:      Maximum sequence length.
        hidden_dim:   Embedding / hidden dimension.
        num_blocks:   Number of Transformer blocks.
        num_heads:    Number of attention heads.
        dropout_rate: Dropout probability.
    """

    def __init__(
        self,
        num_items: int,
        max_len: int,
        hidden_dim: int = 64,
        num_blocks: int = 2,
        num_heads: int = 1,
        dropout_rate: float = 0.2,
    ):
        super().__init__()
        self.item_emb = nn.Embedding(num_items, hidden_dim, padding_idx=0)
        self.pos_emb = nn.Embedding(max_len, hidden_dim)
        self.emb_dropout = nn.Dropout(p=dropout_rate)

        self.blocks = nn.ModuleList([
            SASRecBlock(hidden_dim, num_heads, dropout_rate)
            for _ in range(num_blocks)
        ])

        self.max_len = max_len
        self.hidden_dim = hidden_dim

        # Initialize weights
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Embedding):
            # Embeddings often work best with small variance initialization in RS
            nn.init.normal_(module.weight, mean=0.0, std=0.01)
        elif isinstance(module, nn.Linear) or isinstance(module, nn.Conv1d):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)

    @staticmethod
    def _causal_mask(length: int) -> torch.Tensor:
        """Upper-triangular True mask → prevents attending to future positions."""
        return torch.triu(torch.ones(length, length, dtype=torch.bool), diagonal=1)

    def forward(self, log_seqs: torch.Tensor) -> torch.Tensor:
        """
        Args:
            log_seqs: (batch_size, seq_len)  — padded item-index sequences
        Returns:
            (batch_size, seq_len, hidden_dim) — contextual representations
        """
        batch_size, seq_len = log_seqs.shape

        # Embeddings
        seqs = self.item_emb(log_seqs)
        positions = torch.arange(seq_len, device=log_seqs.device).unsqueeze(0).expand(batch_size, -1)
        seqs = seqs + self.pos_emb(positions)
        seqs = self.emb_dropout(seqs)

        # Masks
        padding_mask = (log_seqs == 0)
        attn_mask = self._causal_mask(seq_len).to(log_seqs.device)

        for block in self.blocks:
            seqs = block(seqs, attn_mask)
            seqs = seqs * (~padding_mask).unsqueeze(-1).float()

        return seqs

    def predict(self, log_seqs: torch.Tensor, item_indices: torch.Tensor) -> torch.Tensor:
        """
        Score candidate items against the last-position representation.

        Args:
            log_seqs:     (batch_size, seq_len)
            item_indices: (batch_size, num_candidates)
        Returns:
            (batch_size, num_candidates)  — logit scores
        """
        seq_out = self.forward(log_seqs)
        final_out = seq_out[:, -1, :]  # (batch_size, hidden_dim)
        item_embs = self.item_emb(item_indices)  # (batch_size, num_candidates, hidden_dim)
        logits = torch.bmm(item_embs, final_out.unsqueeze(-1)).squeeze(-1)
        return logits
