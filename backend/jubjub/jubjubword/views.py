from django.shortcuts import render
from django.http import FileResponse, Http404
from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone
import os
import subprocess
import hashlib
import tempfile
from pathlib import Path
import random
import uuid

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .markov import get_markov_instance
from .models import JubJubWord, WordDefinition, WordInteraction


def get_or_create_session_id(request):
    """Get or create a session ID for anonymous users"""
    session_id = request.session.get('jubjub_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session['jubjub_session_id'] = session_id
        request.session.set_expiry(86400 * 365)  # 1 year
    return session_id


@api_view(['POST'])
def generate_words(request):
    """API endpoint to generate nonsense words with community features"""
    try:
        session_id = get_or_create_session_id(request)
        
        # Get the last shown word from session
        last_word = request.session.get('last_word', None)
        
        # grab parameters from request
        count = request.data.get('count', 1)
        length = request.data.get('length', 8)
        min_length = request.data.get('min_length', 3)
        seed = request.data.get('seed', None)
        temperature = request.data.get('temperature', 1.0)
        n = request.data.get('n', 2)
        use_word_boundaries = request.data.get('use_word_boundaries', True)
        syllable_awareness = request.data.get('syllable_awareness', 0.0)

        # Validate parameters
        count = max(1, min(int(count), 50))
        length = max(3, min(int(length), 20))
        min_length = max(1, min(int(min_length), length))
        temperature = max(0.1, min(float(temperature), 3.0))
        n = max(1, min(int(n), 4))
        syllable_awareness = max(0.0, min(float(syllable_awareness), 1.0))

        # 50/50 chance to show community word vs generate new
        use_community = random.random() < 0.5
        
        if use_community and not seed:  # Don't use community words if user provided seed
            # Try to get a popular community word, excluding the last shown word
            query = JubJubWord.objects.filter(copy_count__gt=0)
            if last_word:
                query = query.exclude(word=last_word)
            
            community_word = query.order_by('-copy_count', '-definition_count', '?').first()
            
            if community_word:
                # Track that we showed this word
                WordInteraction.objects.create(
                    word=community_word,
                    session_id=session_id,
                    interaction_type='shown'
                )
                
                # Update last shown time
                community_word.last_shown = timezone.now()
                community_word.save(update_fields=['last_shown'])
                
                # Store this word as the last shown
                request.session['last_word'] = community_word.word
                
                # Get definitions
                definitions = community_word.definitions.all()[:5]  # Top 5 definitions
                
                return Response({
                    'words': [community_word.word],
                    'is_community': True,
                    'community_data': {
                        'word_id': community_word.id,
                        'copy_count': community_word.copy_count,
                        'definitions': [{
                            'id': d.id,
                            'definition': d.definition,
                            'upvotes': d.upvotes,
                            'downvotes': d.downvotes,
                            'created_at': d.created_at.isoformat(),
                        } for d in definitions]
                    },
                    'parameters': {
                        'count': count,
                        'length': length,
                        'min_length': min_length,
                        'seed': seed,
                        'temperature': temperature,
                        'n': n,
                        'use_word_boundaries': use_word_boundaries,
                        'syllable_awareness': syllable_awareness
                    }
                })

        # Generate new word(s)
        markov = get_markov_instance(n=n, use_word_boundaries=use_word_boundaries)

        words = []
        attempts = 0
        max_attempts = 10
        
        while len(words) < count and attempts < max_attempts:
            attempts += 1
            
            word = markov.genny(
                max_length=length, 
                min_length=min_length,
                seed=seed, 
                temperature=temperature,
                syllable_awareness=syllable_awareness
            )
            
            # Skip if it's the same as the last word
            if word == last_word and attempts < max_attempts:
                continue
                
            words.append(word)
            
            # Store the generated word
            jubjub_word, created = JubJubWord.objects.get_or_create(
                word=word,
                defaults={
                    'temperature': temperature,
                    'markov_order': n,
                    'syllable_awareness': syllable_awareness,
                }
            )
            
            # Track generation
            WordInteraction.objects.create(
                word=jubjub_word,
                session_id=session_id,
                interaction_type='generate'
            )
            
            # Store this word as the last shown
            request.session['last_word'] = word

        return Response({
            'words': words,
            'is_community': False,
            'parameters': {
                'count': count,
                'length': length,
                'min_length': min_length,
                'seed': seed,
                'temperature': temperature,
                'n': n,
                'use_word_boundaries': use_word_boundaries,
                'syllable_awareness': syllable_awareness
            }
        })

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
def track_copy(request):
    """Track when a user copies a word"""
    try:
        session_id = get_or_create_session_id(request)
        word_text = request.data.get('word', '').strip()
        
        if not word_text:
            return Response({'error': 'No word provided'}, status=400)
        
        # Get or create the word
        word, created = JubJubWord.objects.get_or_create(word=word_text)
        
        # Increment copy count
        word.copy_count = F('copy_count') + 1
        word.save(update_fields=['copy_count'])
        
        # Track interaction
        WordInteraction.objects.create(
            word=word,
            session_id=session_id,
            interaction_type='copy'
        )
        
        return Response({
            'success': True,
            'copy_count': word.copy_count
        })
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def add_definition(request):
    """Add a definition to a word"""
    try:
        session_id = get_or_create_session_id(request)
        word_text = request.data.get('word', '').strip()
        definition_text = request.data.get('definition', '').strip()
        
        if not word_text or not definition_text:
            return Response({'error': 'Word and definition required'}, status=400)
        
        # Get or create the word
        word, created = JubJubWord.objects.get_or_create(word=word_text)
        
        # Create the definition
        definition = WordDefinition.objects.create(
            word=word,
            definition=definition_text,
            session_id=session_id
        )
        
        # Update definition count
        word.definition_count = F('definition_count') + 1
        word.save(update_fields=['definition_count'])
        
        # Track interaction
        WordInteraction.objects.create(
            word=word,
            session_id=session_id,
            interaction_type='define',
            definition=definition
        )
        
        return Response({
            'success': True,
            'definition_id': definition.id,
            'definition': {
                'id': definition.id,
                'definition': definition.definition,
                'upvotes': definition.upvotes,
                'downvotes': definition.downvotes,
                'created_at': definition.created_at.isoformat(),
            }
        })
    
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def vote_definition(request):
    """Vote on a definition"""
    try:
        session_id = get_or_create_session_id(request)
        definition_id = request.data.get('definition_id')
        vote_type = request.data.get('vote_type')  # 'up' or 'down'
        
        if not definition_id or vote_type not in ['up', 'down']:
            return Response({'error': 'Invalid vote data'}, status=400)
        
        definition = WordDefinition.objects.get(id=definition_id)
        
        # Check if user already voted
        interaction_type = f"{vote_type}vote"
        existing_vote = WordInteraction.objects.filter(
            session_id=session_id,
            definition=definition,
            interaction_type__in=['upvote', 'downvote']
        ).first()
        
        if existing_vote:
            # Remove old vote
            if existing_vote.interaction_type == 'upvote':
                definition.upvotes = F('upvotes') - 1
            else:
                definition.downvotes = F('downvotes') - 1
            existing_vote.delete()
        
        # Add new vote if not just removing
        if not existing_vote or existing_vote.interaction_type != interaction_type:
            if vote_type == 'up':
                definition.upvotes = F('upvotes') + 1
            else:
                definition.downvotes = F('downvotes') + 1
            
            WordInteraction.objects.create(
                word=definition.word,
                session_id=session_id,
                interaction_type=interaction_type,
                definition=definition
            )
        
        definition.save()
        definition.refresh_from_db()
        
        return Response({
            'success': True,
            'upvotes': definition.upvotes,
            'downvotes': definition.downvotes
        })
    
    except WordDefinition.DoesNotExist:
        return Response({'error': 'Definition not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_word_definitions(request, word):
    """Get all definitions for a word"""
    try:
        jubjub_word = JubJubWord.objects.get(word=word)
        definitions = jubjub_word.definitions.all()[:10]  # Top 10
        
        return Response({
            'word': word,
            'definitions': [{
                'id': d.id,
                'definition': d.definition,
                'upvotes': d.upvotes,
                'downvotes': d.downvotes,
                'created_at': d.created_at.isoformat(),
            } for d in definitions]
        })
    
    except JubJubWord.DoesNotExist:
        return Response({'definitions': []})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def generate_audio(request):
    """Generate audio pronunciation for a word using espeak-ng"""
    # ... existing code ...


@api_view(['GET'])
def health_check(request):
    """Health check endpoint"""
    return Response({'status': 'healthy'})