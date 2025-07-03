'use client';

import { useState, useRef, useEffect } from 'react';
import { wordGeneratorApi } from '@/services/api';
import { GenerateWordsRequest, Definition, CommunityData } from '@/types';

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

// Definition Modal Component
const DefinitionModal = ({ 
  isOpen, 
  onClose, 
  word, 
  onSubmit 
}: { 
  isOpen: boolean; 
  onClose: () => void; 
  word: string; 
  onSubmit: (definition: string) => void;
}) => {
  const [definition, setDefinition] = useState('');
  const [submitting, setSubmitting] = useState(false);
  
  if (!isOpen) return null;
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!definition.trim()) return;
    
    setSubmitting(true);
    await onSubmit(definition);
    setDefinition('');
    setSubmitting(false);
    onClose();
  };
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
        <h3 className="text-2xl font-bold mb-2">{word}</h3>
        <p className="text-gray-600 mb-4">Add your definition for this JubJub word</p>
        
        <form onSubmit={handleSubmit}>
          <textarea
            value={definition}
            onChange={(e) => setDefinition(e.target.value)}
            placeholder="define this word, man"
            className="w-full p-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-pink-400 resize-none"
            rows={4}
            maxLength={500}
            autoFocus
          />
          
          <div className="flex justify-between items-center mt-4">
            <span className="text-sm text-gray-500">
              {definition.length}/500
            </span>
            
            <div className="space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!definition.trim() || submitting}
                className="px-4 py-2 bg-pink-600 text-white rounded-md hover:bg-pink-700 disabled:bg-gray-300 transition-colors"
              >
                {submitting ? 'Adding...' : 'Add Definition'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

// Definition Display Component
const DefinitionDisplay = ({ 
  definitions, 
  onVote 
}: { 
  definitions: Definition[]; 
  onVote: (definitionId: number, voteType: 'up' | 'down') => void;
}) => {
  if (!definitions || definitions.length === 0) return null;
  
  return (
    <div className="mt-8 max-w-2xl mx-auto">
      <h3 className="text-xl font-bold mb-4 text-gray-800">Community Definitions</h3>
      <div className="space-y-4">
        {definitions.map((def, index) => (
          <div key={def.id} className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 text-left">
                <span className="text-sm text-gray-500 mr-2">{index + 1}.</span>
                <span className="text-gray-800">{def.definition}</span>
              </div>
              
              <div className="flex flex-col items-center">
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => onVote(def.id, 'up')}
                    className="text-gray-500 hover:text-green-600 transition-colors"
                    title="Upvote"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                    </svg>
                  </button>
                  <span className="text-sm font-medium text-gray-600 min-w-[2ch] text-center">
                    {def.upvotes - def.downvotes}
                  </span>
                  <button
                    onClick={() => onVote(def.id, 'down')}
                    className="text-gray-500 hover:text-red-600 transition-colors"
                    title="Downvote"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {new Date(def.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
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
  const [showDefinitionModal, setShowDefinitionModal] = useState(false);
  const [isCommunityWord, setIsCommunityWord] = useState(false);
  const [communityData, setCommunityData] = useState<CommunityData | null>(null);
  
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
    setCommunityData(null);
    setIsCommunityWord(false);
    
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
      
      // Check if it's a community word
      if (response.is_community && response.community_data) {
        setIsCommunityWord(true);
        setCommunityData(response.community_data);
      }
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
        
        // Track the copy
        wordGeneratorApi.trackCopy(words[0]).catch(console.error);
        
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
  
  const handleAddDefinition = async (definition: string) => {
    if (words.length === 0) return;
    
    try {
      const result = await wordGeneratorApi.addDefinition(words[0], definition);
      
      // Update community data if we have it
      if (communityData) {
        setCommunityData({
          ...communityData,
          definitions: [result.definition, ...communityData.definitions]
        });
      } else {
        // Convert to community word
        setIsCommunityWord(true);
        setCommunityData({
          word_id: 0, // We don't have this from the API yet
          copy_count: 0,
          definitions: [result.definition]
        });
      }
    } catch (err) {
      console.error('Failed to add definition:', err);
    }
  };
  
  const handleVote = async (definitionId: number, voteType: 'up' | 'down') => {
    try {
      const result = await wordGeneratorApi.voteDefinition(definitionId, voteType);
      
      // Update local state
      if (communityData) {
        setCommunityData({
          ...communityData,
          definitions: communityData.definitions.map(def => 
            def.id === definitionId 
              ? { ...def, upvotes: result.upvotes, downvotes: result.downvotes }
              : def
          )
        });
      }
    } catch (err) {
      console.error('Failed to vote:', err);
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
              
              {/* Community word badge */}
              {isCommunityWord && (
                <div className="inline-flex items-center px-3 py-1 bg-pink-100 text-pink-800 text-sm rounded-full mt-3 mb-2">
                  <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  Community Favorite
                </div>
              )}
              
              {/* Action buttons */}
              <div className="flex justify-center items-center space-x-4 mt-4">
                {/* Pronunciation button */}
                {speechSupported && (
                  <button
                    onClick={handleSpeak}
                    className="p-2 text-gray-600 hover:text-pink-600 transition-colors duration-200 group"
                    title="Pronounce word"
                    disabled={speaking}
                  >
                    <SpeakerIcon speaking={speaking} />
                  </button>
                )}
                
                {/* Add definition button */}
                <button
                  onClick={() => setShowDefinitionModal(true)}
                  className="p-2 text-gray-600 hover:text-pink-600 transition-colors duration-200"
                  title="Add definition"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                </button>
              </div>
              
              <div className="text-gray-500 text-sm mt-2">
                click the word to copy it
              </div>
              
              {/* Community definitions */}
              {communityData && communityData.definitions.length > 0 && (
                <DefinitionDisplay 
                  definitions={communityData.definitions}
                  onVote={handleVote}
                />
              )}
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
      
      {/* Definition Modal */}
      <DefinitionModal 
        isOpen={showDefinitionModal}
        onClose={() => setShowDefinitionModal(false)}
        word={words[0] || ''}
        onSubmit={handleAddDefinition}
      />
    </div>
  );
}