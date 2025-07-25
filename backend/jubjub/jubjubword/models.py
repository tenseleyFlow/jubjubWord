from django.db import models
from django.utils import timezone
import uuid


class Corpus(models.Model):
    """Corpus metadata - actual words are stored in files"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    
    # Theme metadata
    theme_color = models.CharField(max_length=7, default='#3A2449')  # Hex color
    icon_emoji = models.CharField(max_length=10, default='🦜')
    
    # File reference (e.g., "scifi.txt")
    filename = models.CharField(max_length=100,
        default="corpus.txt",
        help_text="Filename in jubjubword directory"
    )
    
    # Stats
    word_count = models.IntegerField(default=0)
    times_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    # Feature flags
    is_active = models.BooleanField(default=True)
    is_premium = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Corpora"
    
    def get_file_path(self):
        """Get the full path to the corpus file"""
        from django.conf import settings
        import os
        return os.path.join(settings.BASE_DIR, 'jubjub', 'jubjubword', self.filename)
    
    def get_words_list(self):
        """Load words from the file"""
        try:
            with open(self.get_file_path(), 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            logger.error(f"Corpus file not found: {self.filename}")
            return []
    
    def update_word_count(self):
        """Update the word count from the file"""
        words = self.get_words_list()
        self.word_count = len(words)
        self.save(update_fields=['word_count'])
        return self.word_count
    
    def __str__(self):
        return self.name
    

class JubJubWord(models.Model):
    """A word that has been generated and potentially defined by the community"""
    word = models.CharField(max_length=50, unique=True, db_index=True)
    syllables = models.CharField(max_length=100, blank=True)  # Store syllable breaks
    
    # Generation parameters (for analytics)
    temperature = models.FloatField(null=True, blank=True)
    markov_order = models.IntegerField(null=True, blank=True)
    syllable_awareness = models.FloatField(null=True, blank=True)
    
    # Popularity metrics
    copy_count = models.IntegerField(default=0)
    definition_count = models.IntegerField(default=0)
    
    # Timestamps
    first_generated = models.DateTimeField(default=timezone.now)
    last_shown = models.DateTimeField(null=True, blank=True)

    corpus = models.ForeignKey(
        Corpus, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='generated_words'
    )
    
    class Meta:
        ordering = ['-copy_count', '-definition_count']
    
    def __str__(self):
        return self.word
    
    @property
    def popularity_score(self):
        """Calculate popularity score for sorting"""
        # Weight copies more than definitions
        return (self.copy_count * 2) + self.definition_count


class WordDefinition(models.Model):
    """User-submitted definitions for JubJub words"""
    word = models.ForeignKey(JubJubWord, on_delete=models.CASCADE, related_name='definitions')
    definition = models.TextField()
    
    # Anonymous user tracking
    session_id = models.CharField(max_length=100, db_index=True)
    
    # Voting
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-upvotes', 'created_at']
    
    def __str__(self):
        return f"{self.word.word}: {self.definition[:50]}..."
    
    @property
    def net_votes(self):
        return self.upvotes - self.downvotes


class WordInteraction(models.Model):
    """Track user interactions with words (copies, votes, etc.)"""
    INTERACTION_TYPES = [
        ('copy', 'Copied Word'),
        ('define', 'Added Definition'),
        ('upvote', 'Upvoted Definition'),
        ('downvote', 'Downvoted Definition'),
        ('generate', 'Generated Word'),
        ('shown', 'Shown Community Word'),
    ]
    
    word = models.ForeignKey(JubJubWord, on_delete=models.CASCADE, related_name='interactions')
    session_id = models.CharField(max_length=100, db_index=True)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    definition = models.ForeignKey(WordDefinition, on_delete=models.CASCADE, null=True, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        # Prevent duplicate votes
        unique_together = [
            ('session_id', 'definition', 'interaction_type'),
        ]
        indexes = [
            models.Index(fields=['session_id', 'created_at']),
            models.Index(fields=['word', 'interaction_type']),
        ]
    
    def __str__(self):
        return f"{self.session_id} - {self.interaction_type} - {self.word.word}"