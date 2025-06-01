from django.shortcuts import render
from django.http import FileResponse, Http404
from django.conf import settings
import os
import subprocess
import hashlib
import tempfile
from pathlib import Path

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .markov import get_markov_instance


@api_view(['POST'])
def generate_words(request):
    """API endpoint to generate nonsense words"""
    try:
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

        # grab markov instance with new parameters
        markov = get_markov_instance(n=n, use_word_boundaries=use_word_boundaries)

        # genny with syllable awareness
        words = []
        for _ in range(count):
            word = markov.genny(
                max_length=length, 
                min_length=min_length,
                seed=seed, 
                temperature=temperature,
                syllable_awareness=syllable_awareness
            )
            words.append(word)

        return Response({
            'words': words,
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
def generate_audio(request):
    """Generate audio pronunciation for a word using espeak-ng"""
    try:
        word = request.data.get('word', '').strip()
        if not word:
            return Response({'error': 'No word provided'}, status=400)

        # sanitize word just in case
        import re
        if not re.match(r'^[a-zA-Z\-\'\.]+$', word):
            return Response({'error': 'Invalid characters in word'}, status=400)

        # create hash for filename (cache audio files)
        word_hash = hashlib.md5(word.lower().encode()).hexdigest()[:8]
        filename = f"word_{word_hash}.wav"

        # Ensure media directory exists
        media_dir = Path(settings.MEDIA_ROOT)
        audio_dir = media_dir / 'audio'
        audio_dir.mkdir(parents=True, exist_ok=True)

        audio_path = audio_dir / filename

        # Check if audio file already exists (cache hit)
        if not audio_path.exists():
            # genny audio using espeak-ng
            try:
                subprocess.run([
                    'espeak-ng',
                    '-w', str(audio_path),  # write to WAV file
                    '-s', '130',            # Speed (words per minute)
                    '-a', '200',            # amplitude (volume)
                    '-g', '5',              # gap between words
                    word
                ], check=True, capture_output=True, text=True)

            except subprocess.CalledProcessError as e:
                return Response({
                    'error': f'Failed to generate audio: {e.stderr}'
                }, status=500)
            except FileNotFoundError:
                return Response({
                    'error': 'espeak-ng not found. Audio generation unavailable.'
                }, status=503)

        # Return URL to the audio file
        audio_url = f"/media/audio/{filename}"

        return Response({
            'word': word,
            'audio_url': audio_url,
            'cached': audio_path.exists()
        })

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def health_check(request):
    """Health check endpoint"""
    return Response({'status': 'healthy'})
