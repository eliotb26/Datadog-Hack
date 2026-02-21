import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Volume2, VolumeX } from 'lucide-react'

const VIDEO_URL = 'https://mojli.s3.us-east-2.amazonaws.com/Mojli+Website+upscaled+(12mb).webm'

export default function Landing() {
  const [muted, setMuted] = useState(true)
  const videoRef = useRef(null)

  const toggleSound = () => {
    const next = !muted
    setMuted(next)
    if (videoRef.current) {
      videoRef.current.muted = next
    }
  }

  return (
    <div className="min-h-screen bg-bg font-sans text-gray-900 antialiased flex flex-col">
      {/* Nav - minimal: logo, sound, CTA */}
      <header className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-6 py-4 md:px-10">
        <Link to="/" className="flex items-center gap-2.5 no-underline text-gray-900">
          <img src="/logo.svg" alt="onlyGen" className="w-8 h-8 flex-shrink-0" />
          <span className="text-base font-extrabold tracking-tight">onlyGen</span>
        </Link>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleSound}
            className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-surface-alt transition-colors"
            title={muted ? 'Turn sound on' : 'Turn sound off'}
            aria-label={muted ? 'Turn sound on' : 'Turn sound off'}
          >
            {muted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
          </button>
          <Link
            to="/app"
            className="inline-flex items-center px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold hover:bg-brand-600 transition-colors no-underline"
          >
            Create your Campaign
          </Link>
        </div>
      </header>

      {/* Video hero with overlay and text on top */}
      <main className="relative flex-1 min-h-[80vh] flex flex-col">
        <div className="absolute inset-0">
          <video
            ref={videoRef}
            src={VIDEO_URL}
            autoPlay
            loop
            playsInline
            muted={muted}
            className="absolute inset-0 w-full h-full object-cover"
            aria-label="Product demo video"
          />
          {/* Shadow overlay so text is clear */}
          <div
            className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/50 to-black/30"
            aria-hidden
          />
        </div>

        {/* Copy and CTA on top of video */}
        <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 py-24 text-center">
          <p className="flex items-center justify-center gap-2 text-sm text-emerald-400 mb-4">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Powered by prediction markets
          </p>
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight max-w-4xl leading-tight mb-5 text-white drop-shadow-sm">
            Content that gets{' '}
            <span className="text-brand-200">smarter</span>{' '}
            every campaign
          </h1>
          <p className="text-lg md:text-xl text-white/90 max-w-2xl mb-10 leading-relaxed drop-shadow-sm">
            OnlyGen uses real-time prediction market data to see what the world is about to care about — then generates, distributes, and optimizes campaigns. Every campaign feeds back so the next one is smarter.
          </p>
          <Link
            to="/app"
            className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-brand text-white font-semibold text-base hover:bg-brand-600 transition-colors no-underline shadow-card-lg"
          >
            Create your Campaign
            <span aria-hidden>→</span>
          </Link>
        </div>

        {/* Metrics bar - below video, app background */}
        <div className="relative z-10 bg-bg border-t border-gray-200">
          <div className="max-w-4xl mx-auto px-6 py-8 grid grid-cols-1 sm:grid-cols-3 gap-8 text-center">
            <div>
              <div className="text-2xl font-bold text-gray-900">3</div>
              <div className="text-sm text-gray-500 mt-1">Self-improving loops</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-gray-900">5</div>
              <div className="text-sm text-gray-500 mt-1">Autonomous agents</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-gray-900">∞</div>
              <div className="text-sm text-gray-500 mt-1">Compounding intelligence</div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
