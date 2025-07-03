from django.db import models
from django.utils import timezone
import uuid


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