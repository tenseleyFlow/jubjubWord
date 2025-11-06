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
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .markov import get_markov_instance
from .models import JubJubWord, WordDefinition, WordInteraction, Corpus

logger = logging.getLogger(__name__)


def get_or_create_session_id(request):
    """Get or create a session ID for anonymous users"""
    session_id = request.session.get('jubjub_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session['jubjub_session_id'] = session_id
        request.session.set_expiry(86400 * 365)  # 1 year
    return session_id


@api_view(['GET'])
def list_corpora(request):
    """List all available corpora"""
    corpora = Corpus.objects.filter(is_active=True).values(
        'slug', 'name', 'description', 'theme_color', 
        'icon_emoji', 'word_count', 'times_used'
    )
    return Response({'corpora': list(corpora)})


@api_view(['POST'])
def generate_words(request):
    """API endpoint to generate nonsense words with corpus selection"""
    try:
        session_id = get_or_create_session_id(request)
        
        # Get the last shown word from session
        last_word = request.session.get('last_word', None)
        
        # Grab parameters from request
        count = request.data.get('count', 1)
        length = request.data.get('length', 8)
        min_length = request.data.get('min_length', 3)
        seed = request.data.get('seed', None)
        temperature = request.data.get('temperature', 1.0)
        n = request.data.get('n', 2)
        use_word_boundaries = request.data.get('use_word_boundaries', True)
        syllable_awareness = request.data.get('syllable_awareness', 0.0)
        corpus_slug = request.data.get('corpus', 'classic')  # NEW PARAMETER

        # Validate parameters
        count = max(1, min(int(count), 50))
        length = max(3, min(int(length), 20))
        min_length = max(1, min(int(min_length), length))
        temperature = max(0.1, min(float(temperature), 3.0))
        n = max(1, min(int(n), 4))
        syllable_awareness = max(0.0, min(float(syllable_awareness), 1.0))

        # Get corpus info
        corpus = None
        try:
            corpus = Corpus.objects.get(slug=corpus_slug, is_active=True)
            # Increment usage counter
            corpus.times_used = F('times_used') + 1
            corpus.save(update_fields=['times_used'])
        except Corpus.DoesNotExist:
            corpus_slug = 'classic'  # Fallback
            logger.warning(f"Corpus '{corpus_slug}' not found, falling back to classic")

        # Community word logic (works for all corpora)
        use_community = random.random() < 0.35 and not seed
        
        # Debug logging
        if use_community:
            total_community_words = JubJubWord.objects.filter(
                copy_count__gt=0,
                corpus__slug=corpus_slug
            ).count()
            logger.info(f"Attempting community word selection from {corpus_slug}. Total available: {total_community_words}")
        
        # Max attempts to avoid infinite loops
        max_generation_attempts = 20
        generation_attempts = 0
        
        while generation_attempts < max_generation_attempts:
            generation_attempts += 1
            
            if use_community:
                # Try to get a popular community word from selected corpus
                query = JubJubWord.objects.filter(
                    Q(copy_count__gt=0) | Q(definition_count__gt=0)
                )
                
                # Filter by corpus if we have one
                if corpus:
                    query = query.filter(corpus=corpus)
                else:
                    # Try to get classic corpus
                    try:
                        classic_corpus = Corpus.objects.get(slug='classic')
                        query = query.filter(corpus=classic_corpus)
                    except Corpus.DoesNotExist:
                        pass
                
                if last_word:
                    query = query.exclude(word=last_word)
                
                # Get multiple candidates to avoid picking the same one
                community_words = list(query.order_by('-copy_count', '-definition_count')[:10])
                if community_words:
                    # Randomly pick from top community words
                    community_word = random.choice(community_words)
                    
                    # Double-check it's not the last word
                    if community_word.word != last_word:
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
                            'corpus': corpus_slug,
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
                                'syllable_awareness': syllable_awareness,
                                'corpus': corpus_slug
                            }
                        })
                
                # If we couldn't find a different community word, fall through to generation
                use_community = False

            # Generate new word with selected corpus
            markov = get_markov_instance(
                n=n, 
                use_word_boundaries=use_word_boundaries,
                corpus_slug=corpus_slug
            )

            word = markov.genny(
                max_length=length, 
                min_length=min_length,
                seed=seed, 
                temperature=temperature,
                syllable_awareness=syllable_awareness
            )
            
            # Check if it's different from the last word
            if word != last_word or generation_attempts >= max_generation_attempts - 1:
                # Store the generated word
                jubjub_word, created = JubJubWord.objects.get_or_create(
                    word=word,
                    defaults={
                        'temperature': temperature,
                        'markov_order': n,
                        'syllable_awareness': syllable_awareness,
                        'corpus': corpus,  # Associate with corpus
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
                    'words': [word],
                    'is_community': False,
                    'corpus': corpus_slug,
                    'parameters': {
                        'count': count,
                        'length': length,
                        'min_length': min_length,
                        'seed': seed,
                        'temperature': temperature,
                        'n': n,
                        'use_word_boundaries': use_word_boundaries,
                        'syllable_awareness': syllable_awareness,
                        'corpus': corpus_slug
                    }
                })
            
            # If we got a duplicate, try again
            # For community words, disable community selection for this attempt
            use_community = False
        
        # Fallback (should rarely reach here)
        return Response({
            'words': ['jubjub'],  # Default fallback word
            'is_community': False,
            'corpus': corpus_slug,
            'parameters': {
                'count': count,
                'length': length,
                'min_length': min_length,
                'seed': seed,
                'temperature': temperature,
                'n': n,
                'use_word_boundaries': use_word_boundaries,
                'syllable_awareness': syllable_awareness,
                'corpus': corpus_slug
            }
        })

    except Exception as e:
        logger.error(f"Error generating words: {str(e)}", exc_info=True)
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
        
        logger.info(f"Track copy called for word: {word_text}")
        
        if not word_text:
            return Response({'error': 'No word provided'}, status=400)
        
        # Get or create the word
        word, created = JubJubWord.objects.get_or_create(word=word_text)
        
        # Increment copy count
        word.copy_count = F('copy_count') + 1
        word.save(update_fields=['copy_count'])
        
        # Refresh to get actual count
        word.refresh_from_db()
        logger.info(f"Word '{word_text}' now has {word.copy_count} copies")
        
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
        logger.error(f"Error tracking copy: {str(e)}")
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
    try:
        word = request.data.get('word', '').strip()
        if not word:
            return Response({'error': 'No word provided'}, status=400)
        
        # Sanitize word for filename
        safe_word = "".join(c for c in word if c.isalnum() or c in '-_').lower()
        if not safe_word:
            safe_word = hashlib.md5(word.encode()).hexdigest()[:10]
        
        # Create media directory if it doesn't exist
        media_dir = Path(settings.MEDIA_ROOT) / 'audio'
        media_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        filename = f"{safe_word}_{hashlib.md5(word.encode()).hexdigest()[:8]}.wav"
        filepath = media_dir / filename
        
        # Check if file already exists
        if filepath.exists():
            return FileResponse(
                open(filepath, 'rb'),
                content_type='audio/wav',
                as_attachment=False
            )
        
        # Generate audio using espeak-ng
        try:
            result = subprocess.run(
                ['espeak-ng', '-w', str(filepath), word],
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"espeak-ng error: {e.stderr}")
            return Response({'error': 'Audio generation failed'}, status=500)
        except FileNotFoundError:
            logger.error("espeak-ng not found")
            return Response({'error': 'Audio generation not available'}, status=503)
        
        # Clean up old files if needed
        audio_files = list(media_dir.glob('*.wav'))
        if len(audio_files) > settings.MAX_AUDIO_FILES:
            # Remove oldest files
            audio_files.sort(key=lambda x: x.stat().st_mtime)
            for old_file in audio_files[:len(audio_files) - settings.MAX_AUDIO_FILES]:
                old_file.unlink()
        
        return FileResponse(
            open(filepath, 'rb'),
            content_type='audio/wav',
            as_attachment=False
        )
    
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def health_check(request):
    """Health check endpoint"""
    return Response({'status': 'healthy'})