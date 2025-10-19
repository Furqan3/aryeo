"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Loader2, Download, Copy, Check } from "lucide-react"
import Image from "next/image"

interface StepFourProps {
  sessionId: string
  heroImage: string
  detailImages: string[]
  onBack: () => void
}

export function StepFour({ sessionId, heroImage, detailImages, onBack }: StepFourProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generatedData, setGeneratedData] = useState<{
    image: string
    caption: string
    hashtags: string[]
  } | null>(null)
  const [copied, setCopied] = useState(false)
  const [saved, setSaved] = useState(false)

  const generateContent = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const propertyInfo = JSON.parse(sessionStorage.getItem("propertyInfo") || "{}")

      const response = await fetch("http://159.203.94.74:8000/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          hero_image_url: heroImage,
          detail_images: detailImages,
          property_info: {
            ...propertyInfo,
            bedrooms: Number.parseInt(propertyInfo.bedrooms),
            bathrooms: Number.parseFloat(propertyInfo.bathrooms),
            square_feet: Number.parseInt(propertyInfo.square_feet),
            year_built: propertyInfo.year_built ? Number.parseInt(propertyInfo.year_built) : null,
          },
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to generate content")
      }

      const data = await response.json()
      const result = {
        image: data.image_base64,
        caption: data.caption,
        hashtags: data.hashtags,
      }
      setGeneratedData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred")
    } finally {
      setLoading(false)
    }
  }, [sessionId, heroImage, detailImages])

  useEffect(() => {
    generateContent()
  }, [generateContent])

  const saveImageToCameraRoll = async () => {
    if (!generatedData) return

    try {
      const base64Data = generatedData.image
      const imageUrl = `data:image/jpeg;base64,${base64Data}`

      // Convert base64 to blob
      const response = await fetch(imageUrl)
      const blob = await response.blob()

      // Check if device supports native share (iOS/Android)
      if (navigator.share && navigator.canShare && navigator.canShare({ files: [new File([blob], 'realty-post.jpg', { type: 'image/jpeg' })] })) {
        const file = new File([blob], `realty-post-${Date.now()}.jpg`, { type: 'image/jpeg' })
        
        await navigator.share({
          files: [file],
          title: 'Save to Photos',
        })
        
        setSaved(true)
        setTimeout(() => setSaved(false), 3000)
      } 
      // Fallback: Try to use the download approach which triggers "Save Image" on mobile browsers
      else {
        const link = document.createElement("a")
        link.href = imageUrl
        link.download = `realty-post-${Date.now()}.jpg`
        
        // For iOS Safari, open in new window which allows saving to photos
        if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
          link.target = "_blank"
        }
        
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        
        setSaved(true)
        setTimeout(() => setSaved(false), 3000)
      }
    } catch (err) {
      console.error('Error saving image:', err)
      // Fallback to regular download
      const link = document.createElement("a")
      link.href = `data:image/jpeg;base64,${generatedData.image}`
      link.download = `realty-post-${Date.now()}.jpg`
      link.click()
    }
  }

  const copyCaption = () => {
    if (!generatedData) return

    const fullText = `${generatedData.caption}\n\n${generatedData.hashtags.join(" ")}`
    navigator.clipboard.writeText(fullText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) {
    return (
      <Card className="p-12 gradient-card border-border">
        <div className="text-center">
          <Loader2 className="w-16 h-16 mx-auto mb-4 animate-spin text-primary" />
          <h3 className="text-2xl font-bold mb-2">Generating Your Post...</h3>
          <p className="text-muted-foreground">Creating professional social media content with AI enhancement</p>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-8 gradient-card border-border">
        <div className="text-center">
          <div className="w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">⚠️</span>
          </div>
          <h3 className="text-2xl font-bold mb-2">Generation Failed</h3>
          <p className="text-muted-foreground mb-6">{error}</p>
          <div className="flex gap-4 justify-center">
            <Button variant="outline" onClick={onBack}>
              Go Back
            </Button>
            <Button onClick={generateContent}>Try Again</Button>
          </div>
        </div>
      </Card>
    )
  }

  if (!generatedData) return null

  return (
    <div className="space-y-6">
      <Card className="p-8 gradient-card border-border">
        <div className="mb-6">
          <h2 className="text-3xl font-bold mb-3">Your Post is Ready! 🎉</h2>
          <p className="text-muted-foreground">Save your image to photos and copy the caption to share on social media</p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Generated Image */}
          <div>
            <h3 className="text-lg font-semibold mb-4">Generated Image</h3>
            <div className="relative aspect-square rounded-lg overflow-hidden border border-border">
              <Image
                src={`data:image/jpeg;base64,${generatedData.image}`}
                alt="Generated post"
                fill
                className="object-cover"
              />
            </div>
            <Button
              onClick={saveImageToCameraRoll}
              className="w-full mt-4 bg-accent hover:bg-accent/90 text-accent-foreground"
              size="lg"
            >
              {saved ? (
                <>
                  <Check className="w-5 h-5 mr-2" />
                  Saved!
                </>
              ) : (
                <>
                  <Download className="w-5 h-5 mr-2" />
                  Save to Photos
                </>
              )}
            </Button>
          </div>

          {/* Caption & Hashtags */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Caption & Hashtags</h3>
              <Button onClick={copyCaption} variant="outline" size="sm">
                {copied ? (
                  <>
                    <Check className="w-4 h-4 mr-2" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4 mr-2" />
                    Copy All
                  </>
                )}
              </Button>
            </div>

            <div className="bg-background rounded-lg p-6 border border-border space-y-4 max-h-[600px] overflow-y-auto">
              <div>
                <h4 className="text-sm font-semibold text-muted-foreground mb-2">CAPTION</h4>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{generatedData.caption}</p>
              </div>

              <div className="border-t border-border pt-4">
                <h4 className="text-sm font-semibold text-muted-foreground mb-2">HASHTAGS</h4>
                <div className="flex flex-wrap gap-2">
                  {generatedData.hashtags.map((tag, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-primary/10 text-primary text-sm rounded-full border border-primary/20"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <div className="flex gap-4">
        <Button variant="outline" onClick={onBack} size="lg" className="flex-1 bg-transparent">
          Back to Edit
        </Button>
        <Button onClick={() => window.location.reload()} size="lg" className="flex-1 bg-primary hover:bg-primary/90">
          Create Another Post
        </Button>
      </div>
    </div>
  )
}
