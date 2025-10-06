"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Sparkles } from "lucide-react"
import { StepOne } from "@/components/step-one"
import { StepTwo } from "@/components/step-two"
import { StepThree } from "@/components/step-three"
import { StepFour } from "@/components/step-four"

export default function Home() {
  const [currentStep, setCurrentStep] = useState(1)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [images, setImages] = useState<string[]>([])
  const [selectedHero, setSelectedHero] = useState<string | null>(null)
  const [selectedDetails, setSelectedDetails] = useState<string[]>([])
  const [url, setUrl] = useState("");
  useEffect(() => {
    setUrl(window.location.href);
    }, []);

  const handleScrapeComplete = (data: { session_id: string; images: string[] }) => {
    setSessionId(data.session_id)
    setImages(data.images)
    setCurrentStep(2)
  }

  const handleImagesSelected = (hero: string, details: string[]) => {
    setSelectedHero(hero)
    setSelectedDetails(details)
    setCurrentStep(3)
  }

  const handlePropertySubmit = () => {
    setCurrentStep(4)
  }

  const resetFlow = () => {
    setCurrentStep(1)
    setSessionId(null)
    setImages([])
    setSelectedHero(null)
    setSelectedDetails([])
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-accent rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-accent-foreground" />
            </div>
            <span className="text-xl font-bold text-balance">RealtyPost</span>
          </div>
          <Button variant="outline" size="sm" onClick={resetFlow}>
            Start Over
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 gradient-hero opacity-10" />
        <div className="container mx-auto px-4 py-16 relative">
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-block mb-4 px-4 py-1.5 bg-primary/10 border border-primary/20 rounded-full">
              <span className="text-sm text-primary font-medium">AI-Powered Content Generator</span>
            </div>
            <h1 className="text-5xl md:text-6xl font-bold mb-6 text-balance">
              Create Stunning Real Estate Posts in Minutes
            </h1>
            <p className="text-xl text-muted-foreground mb-8 text-pretty leading-relaxed">
              Transform your Aryeo listings into professional social media content. Scrape images, customize layouts,
              and generate Instagram-ready posts instantly.
            </p>
          </div>
        </div>
      </section>

      {/* Progress Steps */}
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-12">
            {[
              { num: 1, label: "Scrape Listing" },
              { num: 2, label: "Select Images" },
              { num: 3, label: "Property Details" },
              { num: 4, label: "Generate Post" },
            ].map((step, idx) => (
              <div key={step.num} className="flex items-center flex-1">
                <div className="flex flex-col items-center flex-1">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all ${
                      currentStep >= step.num
                        ? "bg-primary text-primary-foreground"
                        : "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {step.num}
                  </div>
                  <span
                    className={`text-sm mt-2 ${currentStep >= step.num ? "text-foreground" : "text-muted-foreground"}`}
                  >
                    {step.label}
                  </span>
                </div>
                {idx < 3 && (
                  <div
                    className={`h-0.5 flex-1 mx-2 transition-all ${
                      currentStep > step.num ? "bg-primary" : "bg-border"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>

          {/* Step Content */}
          <div className="min-h-[500px]">
            {currentStep === 1 && <StepOne onComplete={handleScrapeComplete} />}
            {currentStep === 2 && (
              <StepTwo images={images} onComplete={handleImagesSelected} onBack={() => setCurrentStep(1)} />
            )}
            {currentStep === 3 && sessionId && selectedHero && selectedDetails.length === 3 && (
              <StepThree onComplete={handlePropertySubmit} onBack={() => setCurrentStep(2)} />
            )}
            {currentStep === 4 && sessionId && selectedHero && selectedDetails.length === 3 && (
              <StepFour
                sessionId={sessionId}
                heroImage={selectedHero}
                detailImages={selectedDetails}
                onBack={() => setCurrentStep(3)}
              />
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-border mt-20">
        <div className="container mx-auto px-4 py-8">
          <div className="text-center text-sm text-muted-foreground">
            <p>© 2025 RealtyPost. Powered by AI for Real Estate Professionals.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
