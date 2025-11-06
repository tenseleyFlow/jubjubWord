"""
Evaluation and comparison tools for hybrid models

Compares:
- Pure Markov generation
- Pure LSTM generation
- Hybrid ensemble generation

Metrics:
- Phonotactic quality (consonant/vowel balance)
- Diversity (unique characters, patterns)
- Corpus similarity (how "on-theme" words are)
- Human preference (subjective, requires annotation)
"""

import numpy as np
from typing import List, Dict, Tuple
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class WordQualityMetrics:
    """
    Automated metrics for evaluating generated words
    """

    def __init__(self):
        self.vowels = set('aeiouAEIOU')
        self.consonants = set('bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ')

    def vowel_consonant_ratio(self, word: str) -> float:
        """
        Calculate vowel to consonant ratio

        Ideal ratio is around 0.4-0.6 for English-like words
        """
        vowel_count = sum(1 for c in word if c in self.vowels)
        consonant_count = sum(1 for c in word if c in self.consonants)

        if consonant_count == 0:
            return 1.0  # All vowels (bad)
        return vowel_count / consonant_count

    def max_consecutive_consonants(self, word: str) -> int:
        """
        Maximum consecutive consonants

        English rarely has >3 consecutive consonants
        """
        max_streak = 0
        current_streak = 0

        for char in word.lower():
            if char in self.consonants:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        return max_streak

    def max_consecutive_vowels(self, word: str) -> int:
        """Maximum consecutive vowels"""
        max_streak = 0
        current_streak = 0

        for char in word.lower():
            if char in self.vowels:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        return max_streak

    def character_diversity(self, word: str) -> float:
        """
        Unique characters / total characters

        Higher = more diverse (but not always better)
        """
        if not word:
            return 0.0
        return len(set(word.lower())) / len(word)

    def bigram_diversity(self, word: str) -> float:
        """
        Unique bigrams / total bigrams

        Measures pattern repetition
        """
        word = word.lower()
        if len(word) < 2:
            return 0.0

        bigrams = [word[i:i+2] for i in range(len(word)-1)]
        return len(set(bigrams)) / len(bigrams)

    def pronounceability_score(self, word: str) -> float:
        """
        Heuristic pronounceability score (0-1)

        Penalizes:
        - Extreme vowel/consonant ratios
        - Long consonant/vowel sequences
        - Very low character diversity
        """
        if not word or len(word) < 2:
            return 0.0

        vc_ratio = self.vowel_consonant_ratio(word)
        max_cons = self.max_consecutive_consonants(word)
        max_vow = self.max_consecutive_vowels(word)
        char_div = self.character_diversity(word)

        # Ideal vowel/consonant ratio is around 0.5
        vc_score = 1.0 - min(abs(vc_ratio - 0.5), 0.5) / 0.5

        # Penalize long sequences
        cons_score = max(0, 1.0 - (max_cons - 3) * 0.2) if max_cons > 3 else 1.0
        vow_score = max(0, 1.0 - (max_vow - 2) * 0.3) if max_vow > 2 else 1.0

        # Encourage moderate diversity
        div_score = min(char_div * 2, 1.0)  # Optimal around 0.5

        # Weighted average
        score = (vc_score * 0.3 + cons_score * 0.3 + vow_score * 0.2 + div_score * 0.2)

        return score

    def evaluate_word(self, word: str) -> Dict:
        """Comprehensive word evaluation"""
        return {
            'word': word,
            'length': len(word),
            'vc_ratio': self.vowel_consonant_ratio(word),
            'max_cons_streak': self.max_consecutive_consonants(word),
            'max_vow_streak': self.max_consecutive_vowels(word),
            'char_diversity': self.character_diversity(word),
            'bigram_diversity': self.bigram_diversity(word),
            'pronounceability': self.pronounceability_score(word)
        }


def compare_generation_methods(markov_instance, hybrid_model,
                              num_samples: int = 100,
                              temperature: float = 1.0,
                              max_length: int = 10) -> Dict:
    """
    Generate words using different methods and compare metrics

    Args:
        markov_instance: Pure Markov model
        hybrid_model: Hybrid Markov-LSTM model
        num_samples: Number of words to generate per method
        temperature: Generation temperature
        max_length: Maximum word length

    Returns:
        Comparison statistics dictionary
    """
    metrics = WordQualityMetrics()

    # Generate words with each method
    markov_words = []
    hybrid_words = []

    logger.info(f"Generating {num_samples} words with each method...")

    for _ in range(num_samples):
        # Pure Markov
        markov_word = markov_instance.genny(
            max_length=max_length,
            temperature=temperature
        )
        markov_words.append(markov_word)

        # Hybrid
        hybrid_word, _ = hybrid_model.generate(
            max_length=max_length,
            temperature=temperature
        )
        hybrid_words.append(hybrid_word)

    # Evaluate each set
    markov_evals = [metrics.evaluate_word(w) for w in markov_words if w]
    hybrid_evals = [metrics.evaluate_word(w) for w in hybrid_words if w]

    # Aggregate statistics
    def aggregate_metrics(evals):
        if not evals:
            return {}

        return {
            'avg_length': np.mean([e['length'] for e in evals]),
            'avg_vc_ratio': np.mean([e['vc_ratio'] for e in evals]),
            'avg_max_cons_streak': np.mean([e['max_cons_streak'] for e in evals]),
            'avg_max_vow_streak': np.mean([e['max_vow_streak'] for e in evals]),
            'avg_char_diversity': np.mean([e['char_diversity'] for e in evals]),
            'avg_bigram_diversity': np.mean([e['bigram_diversity'] for e in evals]),
            'avg_pronounceability': np.mean([e['pronounceability'] for e in evals]),
            'unique_words': len(set([e['word'] for e in evals])),
            'unique_ratio': len(set([e['word'] for e in evals])) / len(evals)
        }

    return {
        'markov': aggregate_metrics(markov_evals),
        'hybrid': aggregate_metrics(hybrid_evals),
        'markov_words': markov_words[:20],  # Sample words
        'hybrid_words': hybrid_words[:20]
    }


def print_comparison_report(comparison: Dict, corpus_name: str = "Unknown"):
    """
    Pretty-print comparison report
    """
    print(f"\n{'='*70}")
    print(f"  Generation Comparison: {corpus_name}")
    print(f"{'='*70}\n")

    markov_stats = comparison['markov']
    hybrid_stats = comparison['hybrid']

    # Create comparison table
    metrics_to_compare = [
        ('Average Length', 'avg_length', '{:.2f}'),
        ('V/C Ratio', 'avg_vc_ratio', '{:.2f}'),
        ('Max Consonant Streak', 'avg_max_cons_streak', '{:.2f}'),
        ('Max Vowel Streak', 'avg_max_vow_streak', '{:.2f}'),
        ('Character Diversity', 'avg_char_diversity', '{:.2f}'),
        ('Bigram Diversity', 'avg_bigram_diversity', '{:.2f}'),
        ('Pronounceability', 'avg_pronounceability', '{:.2f}'),
        ('Unique Words', 'unique_words', '{:d}'),
        ('Unique Ratio', 'unique_ratio', '{:.2%}'),
    ]

    print(f"{'Metric':<25} {'Markov':>15} {'Hybrid':>15} {'Difference':>15}")
    print(f"{'-'*70}")

    for name, key, fmt in metrics_to_compare:
        markov_val = markov_stats.get(key, 0)
        hybrid_val = hybrid_stats.get(key, 0)

        if isinstance(markov_val, int):
            diff = hybrid_val - markov_val
            diff_str = f"{diff:+d}"
        else:
            diff = hybrid_val - markov_val
            diff_str = f"{diff:+.2f}"

        print(f"{name:<25} {fmt.format(markov_val):>15} {fmt.format(hybrid_val):>15} {diff_str:>15}")

    # Sample words
    print(f"\n{'='*70}")
    print(f"  Sample Words")
    print(f"{'='*70}\n")

    print(f"{'Markov':<35} {'Hybrid':<35}")
    print(f"{'-'*70}")

    for markov_word, hybrid_word in zip(comparison['markov_words'][:10],
                                         comparison['hybrid_words'][:10]):
        print(f"{markov_word:<35} {hybrid_word:<35}")

    print(f"\n{'='*70}\n")


def analyze_hybrid_contributions(hybrid_model, num_samples: int = 20,
                                max_length: int = 10) -> Dict:
    """
    Analyze how much Markov vs LSTM contributes to generations

    Returns:
        Statistics about model contributions
    """
    all_metadata = []

    for _ in range(num_samples):
        word, metadata = hybrid_model.generate(max_length=max_length)
        all_metadata.append(metadata)

    # Aggregate metadata
    avg_lstm_confidence = np.mean([m.get('avg_lstm_confidence', 0) for m in all_metadata])
    avg_markov_influence = np.mean([m.get('avg_markov_influence', 0) for m in all_metadata])
    avg_lstm_influence = np.mean([m.get('avg_lstm_influence', 0) for m in all_metadata])

    return {
        'avg_lstm_confidence': avg_lstm_confidence,
        'avg_markov_influence': avg_markov_influence,
        'avg_lstm_influence': avg_lstm_influence,
        'samples': all_metadata[:5]  # Keep some samples for inspection
    }


def print_contribution_analysis(analysis: Dict):
    """Print hybrid contribution analysis"""
    print(f"\n{'='*70}")
    print(f"  Hybrid Model Contribution Analysis")
    print(f"{'='*70}\n")

    print(f"Average LSTM Confidence: {analysis['avg_lstm_confidence']:.2%}")
    print(f"Average Markov Influence: {analysis['avg_markov_influence']:.2%}")
    print(f"Average LSTM Influence: {analysis['avg_lstm_influence']:.2%}")

    print(f"\n{'='*70}")
    print(f"  Sample Generation Traces")
    print(f"{'='*70}\n")

    for i, sample in enumerate(analysis['samples'], 1):
        print(f"Sample {i}:")
        print(f"  Characters: {''.join(sample['characters'])}")
        print(f"  Avg LSTM confidence: {sample.get('avg_lstm_confidence', 0):.2%}")
        print(f"  Avg Markov influence: {sample.get('avg_markov_influence', 0):.2%}")
        print(f"  Avg LSTM influence: {sample.get('avg_lstm_influence', 0):.2%}")
        print()
