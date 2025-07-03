'use client';

import { useState, useRef, useEffect } from 'react';
import { wordGeneratorApi } from '@/services/api';
import { GenerateWordsRequest } from '@/types';

import BirdIcon from '@/assets/puffin.svg';

// Simple syllable detection based on vowel patterns
function getSyllableBreaks(word: string): string {
  const vowels = 'aeiouAEIOU';
  const syllables: string[] = [];
  let currentSyllable = '';
  
  for (let i = 0; i < word.length; i++) {
    const char = word[i];
    const isVowel = vowels.includes(char);
    const nextChar = word[i + 1];
    const isNextVowel = nextChar && vowels.includes(nextChar);
    
    currentSyllable += char;
    
    // Break syllable after vowel followed by consonant (unless at end)
    if (isVowel && !isNextVowel && i < word.length - 1) {
      // Look ahead for consonant clusters
      let consonantCount = 0;
      for (let j = i + 1; j < word.length && !vowels.includes(word[j]); j++) {
        consonantCount++;
      }
      
      // If multiple consonants, keep first with current syllable
      if (consonantCount > 1 && i < word.length - 2) {
        currentSyllable += word[i + 1];
        i++;
      }
      
      syllables.push(currentSyllable);
      currentSyllable = '';
    } else if (i === word.length - 1) {
      // Add remaining
      syllables.push(currentSyllable);
    }
  }
  
  // Handle any remaining characters
  if (currentSyllable) {
    if (syllables.length > 0 && currentSyllable.length === 1 && !vowels.includes(currentSyllable)) {
      // Attach single consonant to previous syllable
      syllables[syllables.length - 1] += currentSyllable;
    } else {
      syllables.push(currentSyllable);
    }
  }
  
  return syllables.join('·');
}

// Speech synthesis hook
function useSpeechSynthesis() {
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState(true);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  
  useEffect(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      synthRef.current = window.speechSynthesis;
    } else {
      setSupported(false);
    }
  }, []);
  
  const speak = (text: string) => {
    if (!synthRef.current || !supported) return;
    
    // Cancel any ongoing speech
    synthRef.current.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.9; // Slightly slower for nonsense words
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    
    synthRef.current.speak(utterance);
  };
  
  const stop = () => {
    if (synthRef.current) {
      synthRef.current.cancel();
      setSpeaking(false);
    }
  };
  
  return { speak, stop, speaking, supported };
}

// Speaker Icon Component
const SpeakerIcon = ({ speaking }: { speaking: boolean }) => {
  if (speaking) {
    return (
      <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    );
  }
  
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
    </svg>
  );
};

export default function Home() {
  const [words, setWords] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shake, setShake] = useState(false);
  const [hasClickedBird, setHasClickedBird] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  // Speech synthesis
  const { speak, stop, speaking, supported: speechSupported } = useSpeechSynthesis();
  
  // Form state
  const count = 1;
  const [length, setLength] = useState(8);
  const [minLength, setMinLength] = useState(3);
  const [seed, setSeed] = useState('');
  const [temperature, setTemperature] = useState(1.0);
  const [markovOrder, setMarkovOrder] = useState(2);
  const [useWordBoundaries, setUseWordBoundaries] = useState(true);
  const [syllableAwareness, setSyllableAwareness] = useState(0.0);

  const handleGenerate = async () => {
    // block multiple clicks during loading
    if (loading) return;
    
    // Stop any ongoing speech
    stop();
    
    // mark bird clicked
    setHasClickedBird(true);
    
    setLoading(true);
    setError(null);
    
    // Trigger shake animation
    setShake(true);
    
    // reset shake after animation completes
    setTimeout(() => setShake(false), 800);
    
    try {
      const params: GenerateWordsRequest = {
        count,
        length,
        min_length: minLength,
        temperature,
        n: markovOrder,
        use_word_boundaries: useWordBoundaries,
        syllable_awareness: syllableAwareness,
        ...(seed && { seed }),
      };
      
      const response = await wordGeneratorApi.generateWords(params);
      setWords(response.words);
    } catch (err) {
      setError('Failed to generate words. Please try again.');
      console.error('Error generating words:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopyWord = async () => {
    if (words.length > 0) {
      try {
        await navigator.clipboard.writeText(words[0]);
        setCopied(true);
        // reset after 2 seconds
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        console.error('Failed to copy text: ', err);
      }
    }
  };

  const handleSpeak = () => {
    if (words.length > 0 && speechSupported) {
      speak(words[0]);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-rose-to-cream">
      <main className="flex-1 p-8 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold mb-2">
              JubJubWord
            </h1>
            <p className='text-gray-500'>for Jules</p>
            <h2 className="text-2xl font-bold mb-2">
              Powered by the <a href="https://www.poetryfoundation.org/poems/42916/jabberwocky" className="no-underline text-inherit">JubJub Bird</a>
            </h2>
            <p className="text-gray-600">
              Generate nonsense words <a href="https://www.youtube.com/watch?v=t18Fpbi1MI0" className="text-pink-600 hover:text-pink-800 underline">à la Ed BassMaster</a> using Markov chains
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
            {/* Basic Controls - with descriptive text */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Length
                  <span className="block text-xs text-gray-500">longest allowed word</span>
                </label>
                <input
                  type="number"
                  min="3"
                  max="20"
                  value={length}
                  onChange={(e) => setLength(parseInt(e.target.value) || 8)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-pink-400"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Temperature
                  <span className="block text-xs text-gray-500">higher = more random</span>
                </label>
                <div className="relative">
                  <input
                    type="range"
                    min="0.1"
                    max="3.0"
                    step="0.1"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
                    style={{
                      background: `linear-gradient(to right, #f472b6 0%, #f472b6 ${((temperature - 0.1) / (3.0 - 0.1)) * 100}%, #e5e7eb ${((temperature - 0.1) / (3.0 - 0.1)) * 100}%, #e5e7eb 100%)`
                    }}
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>conservative</span>
                    <span className="font-medium">{temperature.toFixed(1)}</span>
                    <span>creative</span>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Syllable Awareness
                  <span className="block text-xs text-gray-500">0 = random, 1 = pronounceable</span>
                </label>
                <div className="relative">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={syllableAwareness}
                    onChange={(e) => setSyllableAwareness(parseFloat(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
                    style={{
                      background: `linear-gradient(to right, #f472b6 0%, #f472b6 ${syllableAwareness * 100}%, #e5e7eb ${syllableAwareness * 100}%, #e5e7eb 100%)`
                    }}
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>random</span>
                    <span className="font-medium">{syllableAwareness.toFixed(1)}</span>
                    <span>natural</span>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Seed (optional)
                  <span className="block text-xs text-gray-500">starting characters</span>
                </label>
                <input
                  type="text"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  placeholder="e.g., 'ju'"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-pink-400"
                />
              </div>
            </div>

            {/* advanced options toggle */}
            <div className="mb-4">
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-sm text-pink-600 hover:text-pink-800 transition-colors flex items-center"
              >
                <span className="mr-1">{showAdvanced ? '▼' : '▶'}</span>
                advanced options
              </button>
            </div>

            {/* Advanced controls - collapsible */}
            {showAdvanced && (
              <div className="border-t pt-4 mb-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Min Length
                      <span className="block text-xs text-gray-500">shortest allowed word</span>
                    </label>
                    <input
                      type="number"
                      min="1"
                      max={length}
                      value={minLength}
                      onChange={(e) => setMinLength(parseInt(e.target.value) || 3)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-pink-400"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Markov Order
                      <span className="block text-xs text-gray-500">characters to look back</span>
                    </label>
                    <select
                      value={markovOrder}
                      onChange={(e) => setMarkovOrder(parseInt(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-pink-400"
                    >
                      <option value={1}>1 (chaotic)</option>
                      <option value={2}>2 (default)</option>
                      <option value={3}>3 (structured)</option>
                      <option value={4}>4 (very structured)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Word Boundaries
                      <span className="block text-xs text-gray-500">use start/end markers</span>
                    </label>
                    <div className="flex items-center h-10">
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={useWordBoundaries}
                          onChange={(e) => setUseWordBoundaries(e.target.checked)}
                          className="mr-2 h-4 w-4 text-pink-600 focus:ring-pink-500 border-gray-300 rounded"
                        />
                        <span className="text-sm text-gray-700">Enabled</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="mt-4 p-4 bg-red-100 border border-red-300 rounded-md">
                <p className="text-red-700">{error}</p>
              </div>
            )}
          </div>

          <div className="flex justify-center mb-6 relative">
            <button
              onClick={handleGenerate}
              disabled={loading}
              aria-label="Generate words"
              className={`text-8xl transition-all duration-200 ${loading ? 'cursor-not-allowed' : 'cursor-pointer'}`}
            >
              {/* outer div handles floating */}
              <div className={`bird-float ${loading ? 'loading' : ''}`}>
                {/* inner the shake */}
                <div className={`bird-shake ${shake ? 'shake' : ''}`}>
                  <BirdIcon
                    width={172}
                    height={172}
                    className="bird-icon"
                  />
                </div>
              </div>

            </button>
            
            {/* prompt - only show if bird hasn't been clicked */}
            {!hasClickedBird && (
              <div className="absolute mt-48 text-gray-500 text-sm animate-pulse">
                click the JubJub Bird!
              </div>
            )}
          </div>

          {words.length > 0 && (
            <div className="text-center">
              <div 
                onClick={handleCopyWord}
                className="text-5xl font-bold text-gray-800 mt-6 cursor-pointer hover:text-pink-600 transition-colors duration-200 select-none relative inline-block"
                title="Click to copy"
              >
                {words[0]}
                {copied && (
                  <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white text-sm px-3 py-1 rounded-lg animate-fade-in-out">
                    copied!
                  </div>
                )}
              </div>
              
              {/* Syllable breaks */}
              <div className="text-lg text-gray-600 mt-2">
                {getSyllableBreaks(words[0])}
              </div>
              
              {/* Pronunciation button */}
              {speechSupported && (
                <button
                  onClick={handleSpeak}
                  className="mt-4 p-2 text-gray-600 hover:text-pink-600 transition-colors duration-200 group"
                  title="Pronounce word"
                  disabled={speaking}
                >
                  <SpeakerIcon speaking={speaking} />
                </button>
              )}
              
              <div className="text-gray-500 text-sm mt-2">
                click the word to copy it
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="border-t border-gray-200 py-4 px-8 flex-shrink-0">
        <div className="max-w-4xl mx-auto">
          <nav className="flex justify-center space-x-8">
            <a href="https://github.com/tenseleyFlow/jubjubWord" target="_blank" rel="noopener noreferrer" className="text-gray-600 hover:text-pink-600 transition-colors text-sm">
              code
            </a>
            <a href="https://raw.githubusercontent.com/tenseleyFlow/jubjubWord/refs/heads/trunk/backend/jubjub/jubjubword/corpus.txt" target="_blank" rel="noopener noreferrer" className="text-gray-600 hover:text-pink-600 transition-colors text-sm">
              corpus
            </a>
            <a href="https://www.poetryfoundation.org/poems/42916/jabberwocky" target="_blank" rel="noopener noreferrer" className="text-gray-600 hover:text-pink-600 transition-colors text-sm">
              jabberwocky
            </a>
            <a href="https://www.musicsian.com" target="_blank" rel="noopener noreferrer" className="text-gray-600 hover:text-pink-600 transition-colors text-sm">
              matt
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}