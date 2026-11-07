import { useState, useRef, useCallback, useEffect } from 'react';
import { api } from '../api';
import './VoiceButton.css';

/**
 * VoiceButton component for voice dictation.
 * Records audio from the microphone and transcribes it using Groq's Whisper API.
 */
export default function VoiceButton({ onTranscription, disabled, disabledReason }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState(null);
  const [showSetupModal, setShowSetupModal] = useState(false);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const startingRef = useRef(false);
  const stoppingRef = useRef(false);

  // Cleanup on unmount - release microphone stream
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.ondataavailable = null;
        mediaRecorderRef.current.onstop = null;
        mediaRecorderRef.current = null;
      }
    };
  }, []);

  const startRecording = useCallback(async () => {
    if (startingRef.current || isRecording || stoppingRef.current) {
      return;
    }

    startingRef.current = true;
    setIsStarting(true);
    setError(null);

    let stream;
    let mediaRecorder;
    try {
      // Request microphone access
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
        }
      });

      // Create MediaRecorder with best available format (Safari compatibility)
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/mp4')
          ? 'audio/mp4'
          : undefined; // Let browser choose default

      mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
      const recordingMimeType = mediaRecorder.mimeType || 'audio/webm';
      const chunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all tracks to release the microphone
        stream.getTracks().forEach(track => track.stop());
        if (streamRef.current === stream) {
          streamRef.current = null;
        }
        if (mediaRecorderRef.current === mediaRecorder) {
          mediaRecorderRef.current = null;
        }

        try {
          if (chunks.length === 0) {
            setError('No audio recorded');
            return;
          }

          const audioBlob = new Blob(chunks, { type: recordingMimeType });

          // Generate filename with correct extension based on MIME type
          const extension = recordingMimeType.includes('mp4') ? 'mp4' : 'webm';
          const filename = `recording.${extension}`;

          // Transcribe the audio
          setIsTranscribing(true);
          try {
            const result = await api.transcribeAudio(audioBlob, filename);
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
        } finally {
          stoppingRef.current = false;
          setIsStopping(false);
        }
      };

      // Store stream for cleanup
      streamRef.current = stream;
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
      if (stream && streamRef.current === stream) {
        streamRef.current = null;
      }
      if (mediaRecorder && mediaRecorderRef.current === mediaRecorder) {
        mediaRecorderRef.current = null;
      }
      console.error('Failed to start recording:', err);
      if (err.name === 'NotAllowedError') {
        setError('Microphone access denied. Please allow microphone access.');
      } else if (err.name === 'NotFoundError') {
        setError('No microphone found. Please connect a microphone.');
      } else {
        setError('Failed to access microphone');
      }
    } finally {
      startingRef.current = false;
      setIsStarting(false);
    }
  }, [isRecording, onTranscription]);

  const stopRecording = useCallback(() => {
    if (stoppingRef.current) {
      return;
    }
    const mediaRecorder = mediaRecorderRef.current;
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      stoppingRef.current = true;
      setIsStopping(true);
      try {
        mediaRecorder.stop();
      } catch (err) {
        stoppingRef.current = false;
        setIsStopping(false);
        console.error('Failed to stop recording:', err);
      }
      setIsRecording(false);
    }
  }, []);

  const handleClick = useCallback(() => {
    if (isStarting || isStopping) {
      return;
    }
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, isStarting, isStopping, startRecording, stopRecording]);

  // Determine button state
  const isDisabled = disabled || isStarting || isStopping || isTranscribing;
  const buttonClass = `voice-button ${isRecording ? 'recording' : ''} ${isTranscribing ? 'transcribing' : ''}`;
  const buttonLabel = disabled && disabledReason
    ? disabledReason
    : isStarting
      ? 'Starting voice dictation...'
      : isRecording
        ? 'Stop recording'
        : isTranscribing || isStopping
          ? 'Transcribing...'
          : 'Start voice dictation';

  return (
    <div className="voice-button-container">
      <button
        type="button"
        className={buttonClass}
        onClick={handleClick}
        disabled={isDisabled}
        title={buttonLabel}
        aria-label={buttonLabel}
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
              type="button"
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
