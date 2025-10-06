"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Check } from "lucide-react"
import Image from "next/image"

interface StepTwoProps {
  images: string[]
  onComplete: (hero: string, details: string[]) => void
  onBack: () => void
}

export function StepTwo({ images, onComplete, onBack }: StepTwoProps) {
  const [selectedHero, setSelectedHero] = useState<string | null>(null)
  const [selectedDetails, setSelectedDetails] = useState<string[]>([])
  const [selectionMode, setSelectionMode] = useState<'hero' | 'details'>('hero')

  const toggleDetailImage = (img: string) => {
    if (selectedDetails.includes(img)) {
      setSelectedDetails(selectedDetails.filter((i) => i !== img))
    } else if (selectedDetails.length < 3) {
      setSelectedDetails([...selectedDetails, img])
    }
  }

  const handleImageClick = (img: string) => {
    if (selectionMode === 'hero') {
      setSelectedHero(img)
    } else {
      toggleDetailImage(img)
    }
  }

  const handleContinue = () => {
    if (selectedHero && selectedDetails.length === 3) {
      onComplete(selectedHero, selectedDetails)
    }
  }

  return (
    <Card className="p-8 gradient-card border-border">
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-3">Select Your Images</h2>
        <p className="text-muted-foreground">Choose 1 hero image and 3 detail images for your social media post</p>
      </div>

      <div className="flex justify-between mb-4">
        <h3 className="text-xl font-semibold flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm">
            1
          </span>
          Hero Image {selectedHero && <Check className="w-5 h-5 text-accent" />}
        </h3>
        <h3 className="text-xl font-semibold flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm">
            2
          </span>
          Detail Images ({selectedDetails.length}/3)
        </h3>
      </div>

      <div className="flex gap-2 mb-4">
        <Button 
          variant={selectionMode === 'hero' ? 'default' : 'outline'} 
          onClick={() => setSelectionMode('hero')}
        >
          Select Hero
        </Button>
        <Button 
          variant={selectionMode === 'details' ? 'default' : 'outline'} 
          onClick={() => setSelectionMode('details')}
        >
          Select Details
        </Button>
      </div>

      {/* Single Image Grid */}
      <div className="mb-8">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {images.map((img, idx) => {
            const isHero = selectedHero === img
            const isDetail = selectedDetails.includes(img)
            const selectionIndex = selectedDetails.indexOf(img)
            const isDisabled = (selectionMode === 'details') && !isDetail && (selectedDetails.length >= 3)

            return (
              <button
                key={idx}
                onClick={() => handleImageClick(img)}
                disabled={isDisabled}
                className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
                  isHero
                    ? "border-primary ring-2 ring-primary/50 hover:scale-105"
                    : isDetail
                      ? "border-accent ring-2 ring-accent/50 hover:scale-105"
                      : isDisabled
                        ? "border-border opacity-50 cursor-not-allowed"
                        : "border-border hover:border-primary/50 hover:scale-105"
                }`}
              >
                <Image 
                  src={img || "/placeholder.svg"} 
                  alt={`Image ${idx + 1}`} 
                  fill 
                  className="object-cover" 
                  unoptimized // ✅ prevent Next.js from proxying the image
                />
                {isHero && (
                  <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                    <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center">
                      <Check className="w-6 h-6 text-primary-foreground" />
                    </div>
                  </div>
                )}
                {isDetail && (
                  <div className="absolute inset-0 bg-accent/20 flex items-center justify-center">
                    <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center">
                      <span className="text-lg font-bold text-accent-foreground">{selectionIndex + 1}</span>
                    </div>
                  </div>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-4">
        <Button variant="outline" onClick={onBack} size="lg" className="flex-1 bg-transparent">
          Back
        </Button>
        <Button
          onClick={handleContinue}
          disabled={!selectedHero || selectedDetails.length !== 3}
          size="lg"
          className="flex-1 bg-primary hover:bg-primary/90"
        >
          Continue to Property Details
        </Button>
      </div>
    </Card>
  )
}