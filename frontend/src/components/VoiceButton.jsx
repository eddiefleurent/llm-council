import { useState, useRef, useCallback } from 'react';
import { api } from '../api';
import './VoiceButton.css';

/**
 * VoiceButton component for voice dictation.
 * Records audio from the microphone and transcribes it using Groq's Whisper API.
 */
export default function VoiceButton({ onTranscription, disabled }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState(null);
  const [showSetupModal, setShowSetupModal] = useState(false);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
        } 
      });

      // Create MediaRecorder with webm format (widely supported)
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });

      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all tracks to release the microphone
        stream.getTracks().forEach(track => track.stop());

        if (chunksRef.current.length === 0) {
          setError('No audio recorded');
          return;
        }

        // Create blob from chunks
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        
        // Transcribe the audio
        setIsTranscribing(true);
        try {
          const result = await api.transcribeAudio(audioBlob, 'recording.webm');
          if (result.text && result.text.trim()) {
            onTranscription(result.text);
          }
        } catch (err) {
          console.error('Transcription error:', err);
          // Check if it's a setup/configuration error (503)
          if (err.message && err.message.includes('GROQ_API_KEY')) {
            setShowSetupModal(true);
          } else {
            setError(err.message || 'Failed to transcribe audio');
          }
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Failed to start recording:', err);
      if (err.name === 'NotAllowedError') {
        setError('Microphone access denied. Please allow microphone access.');
      } else if (err.name === 'NotFoundError') {
        setError('No microphone found. Please connect a microphone.');
      } else {
        setError('Failed to access microphone');
      }
    }
  }, [onTranscription]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, []);

  const handleClick = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Determine button state
  const isDisabled = disabled || isTranscribing;
  const buttonClass = `voice-button ${isRecording ? 'recording' : ''} ${isTranscribing ? 'transcribing' : ''}`;

  return (
    <div className="voice-button-container">
      <button
        type="button"
        className={buttonClass}
        onClick={handleClick}
        disabled={isDisabled}
        title={isRecording ? 'Stop recording' : isTranscribing ? 'Transcribing...' : 'Start voice dictation'}
        aria-label={isRecording ? 'Stop recording' : 'Start voice dictation'}
      >
        {isTranscribing ? (
          <span className="voice-spinner"></span>
        ) : isRecording ? (
          // Stop icon (square)
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          // Microphone icon
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        )}
      </button>
      {error && (
        <div className="voice-error" role="alert">
          {error}
        </div>
      )}
      
      {/* Setup Modal for missing GROQ_API_KEY */}
      {showSetupModal && (
        <div className="voice-modal-overlay" onClick={() => setShowSetupModal(false)}>
          <div className="voice-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Voice Transcription Setup</h3>
            <p>
              Voice dictation requires a Groq API key for speech-to-text transcription.
            </p>
            <ol>
              <li>
                Get a free API key at{' '}
                <a 
                  href="https://console.groq.com/keys" 
                  target="_blank" 
                  rel="noopener noreferrer"
                >
                  console.groq.com/keys
                </a>
              </li>
              <li>
                Add to your <code>.env</code> file:
                <pre>GROQ_API_KEY=your_key_here</pre>
              </li>
              <li>Restart the backend server</li>
            </ol>
            <button 
              className="voice-modal-close"
              onClick={() => setShowSetupModal(false)}
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
