import os
import random
import logging
from django.conf import settings
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class Marklove:
    """
    Markov Chain plausible nonsense word generator, now, nOW, NOW! with 
    improved seed handling and performance.
    """

    def __init__(self, n: int = 2, use_word_boundaries: bool = True):
        """
        Initialize the Markov chain.

        Args:
            n: Order of the Markov chain (number of characters for state)
            use_word_boundaries: Whether to add start/end markers to words
        """
        # Ensure n is at least 1
        self.n = max(1, n)
        self.use_word_boundaries = use_word_boundaries
        self.transitions: Dict[str, List[str]] = defaultdict(list)
        
        # States that can start words
        self.start_states: List[str] = []
        self.trained = False

        # Boundary markers
        self.start_marker = "^"
        self.end_marker = "$"

    def train(self, lines: List[str]) -> None:
        """
        build the Markov chain from a list of lines/words.

        Args:
            lines: List of words/lines to train on
        """
        self.transitions.clear()
        self.start_states.clear()

        valid_words = []

        for line in lines:
            # Normalize to lowercase
            text = line.strip().lower()
            if not text or len(text) < self.n:
                continue
            valid_words.append(text)

        if not valid_words:
            logger.warning("No valid words found for training")
            return

        for word in valid_words:
            processed_word = self._prepare_word(word)
            self._extract_transitions(processed_word)

        self.trained = True
        logger.info(f"Trained on {len(valid_words)} words, " +
                    f"{len(self.transitions)} unique states")

    def _prepare_word(self, word: str) -> str:
        """Add boundary markers if enabled."""
        if self.use_word_boundaries:
            return self.start_marker * self.n + word + self.end_marker * self.n
        return word

    def _extract_transitions(self, text: str) -> None:
        """extract state transitions from a prepared word."""
        for i in range(len(text) - self.n):
            state = text[i:i + self.n]
            next_char = text[i + self.n]

            self.transitions[state].append(next_char)

            # Track start states (for unseeded generation)
            if (self.use_word_boundaries and
                    state.startswith(self.start_marker * self.n)):
                if state not in self.start_states:
                    self.start_states.append(state)

    def genny(self, max_length: int = 10, min_length: int = 3, 
              seed: Optional[str] = None, temperature: float = 1.0) -> str:
        """
        Generate a nonsense word using the trained Markov Chain.

        Args:
            max_length: Maximum length of generated word
            min_length: minimum length of generated word
            seed: optional seed to influence generation
            temperature: Randomness control (higher = more random)

        Returns:
            plausibly deniable nonsense word
        """
        if not self.trained or not self.transitions:
            return ""

        max_length = max(min_length, max_length)
        state = self._get_initial_state(seed)

        if not state:
            return ""

        output = []
        current_state = state
        attempts = 0
        max_attempts = max_length * 3

        while len(output) < max_length and attempts < max_attempts:
            attempts += 1

            possible_chars = self.transitions.get(current_state, [])
            if not possible_chars:
                break

            next_char = self._weighted_choice(possible_chars, temperature)

            # Check for end marker
            if self.use_word_boundaries and next_char == self.end_marker:
                if len(output) >= min_length:
                    break
                # If too short, try to continue without the end marker
                possible_chars = [c for c in possible_chars if c != self.end_marker]
                if not possible_chars:
                    break
                next_char = self._weighted_choice(possible_chars, temperature)

            output.append(next_char)
            current_state = current_state[1:] + next_char

        # Clean up the output
        result = "".join(output)
        if self.use_word_boundaries:
            result = result.replace(self.start_marker, "").replace(self.end_marker, "")

        return result

    def _get_initial_state(self, seed: Optional[str]) -> Optional[str]:
        """
        grab the initial state for word generation.

        Args:
            seed: optional seed string

        Returns:
            initial state string or None if no valid state found
        """
        if not seed:
            if self.start_states:
                return random.choice(self.start_states)
            return random.choice(list(self.transitions.keys()))

        # Normalize seed
        seed = seed.lower().strip()

        # Try to find states that match the seed pattern
        matching_states = self._find_matching_states(seed)
        if matching_states:
            return random.choice(matching_states)

        # Fallback: try to create a state from the seed (without boundaries)
        if len(seed) >= self.n:
            candidate = seed[:self.n]
            if candidate in self.transitions:
                return candidate

        # If seed is shorter than n, try to find states that start with the seed
        for state in self.transitions.keys():
            clean_state = state.replace(self.start_marker, "").replace(self.end_marker, "")
            if clean_state.startswith(seed):
                return state

        # Last resort: random state
        logger.warning(f"No matching state found for seed '{seed}'," +
                        " using random state")
        if self.start_states:
            return random.choice(self.start_states)
        return random.choice(list(self.transitions.keys()))


    def _find_matching_states(self, seed: str) -> List[str]:
        """
        find states that match or contain the seed.

        Args:
            seed: Seed string to match

        Returns:
            List of matching states
        """
        matching_states = []

        for state in self.transitions.keys():
            clean_state = state.replace(self.start_marker, "").replace(self.end_marker, "")

            # Exact match
            if clean_state == seed[:len(clean_state)]:
                matching_states.append(state)
            # Partial match (state starts with seed)
            elif clean_state.startswith(seed):
                matching_states.append(state)
            # Contains seed
            elif seed in clean_state:
                matching_states.append(state)

        return matching_states

    def _weighted_choice(self, chars: List[str], temperature: float) -> str:
        """
        Optimized weighted choice w. temperature control.

        Args:
            chars: List of character choices
            temperature: Temperature parameter

        Returns:
            Selected character
        """
        # no no no
        # divide by zero
        if temperature <= 0:
            temperature = 0.01

        # Use Counter for efficient frequency counting
        char_freq = Counter(chars)
        chars_list = list(char_freq.keys())

        if temperature == 1.0:
            frequencies = list(char_freq.values())
        else:
            frequencies = [freq ** (1 / temperature) for freq in char_freq.values()]

        return random.choices(chars_list, weights=frequencies)[0]

    def get_statistics(self) -> Dict:
        """Get statistics about the trained model."""
        if not self.trained:
            return {"error": "Model not trained"}

        return {
            "num_states": len(self.transitions),
            "num_start_states": len(self.start_states),
            "avg_transitions_per_state": sum(len(v) for v in self.transitions.values()) / len(self.transitions),
            "markov_order": self.n,
            "uses_word_boundaries": self.use_word_boundaries
        }


# global instance management
_markov_instances: Dict[Tuple[int, bool], Marklove] = {}


def get_markov_instance(n: int = 2, use_word_boundaries: bool = True) -> Marklove:
    """
    grab or create a Markov instance with specified parameters.

    Args:
        n: Order of the Markov chain
        use_word_boundaries: Whether to use word boundaries

    Returns:
        Markov instance
    """
    key = (n, use_word_boundaries)

    if key not in _markov_instances:
        instance = Marklove(n=n, use_word_boundaries=use_word_boundaries)

        # load corpus
        corpus_path = os.path.join(settings.BASE_DIR, 'jubjub', 'jubjubword', 'corpus.txt')
        try:
            with open(corpus_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            logger.info(f"Loaded corpus with {len(lines)} lines")
        except FileNotFoundError:
            logger.warning(f"Corpus file not found at {corpus_path}, using fallback")
            lines = ["bartledoo", "malt-lickey", "schnoodleflop", "jubjub", "galumph"]

        instance.train(lines)
        _markov_instances[key] = instance

    return _markov_instances[key]


def clear_cache():
    """Clear the cached Markov instances."""
    global _markov_instances
    _markov_instances.clear()
