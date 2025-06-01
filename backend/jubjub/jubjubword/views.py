from django.shortcuts import render

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

        # Validate parameters:
        #       - Limit to 50 words
        #       - Limit length
        #       - Add this
        #       - Limit temperature to reasonable range
        #       - Clamp syllable awareness
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


@api_view(['GET'])
def health_check(request):
    """Health check endpoint"""
    return Response({'status': 'healthy'})
