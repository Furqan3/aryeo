"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Loader2, LinkIcon, AlertCircle } from "lucide-react"

interface StepOneProps {
  onComplete: (data: { session_id: string; images: string[] }) => void
}

export function StepOne({ onComplete }: StepOneProps) {
  const [url, setUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const response = await fetch("http://159.203.94.74:8000/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listing_url: url }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to scrape listing")
      }

      const data = await response.json()
      onComplete(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-8 gradient-card border-border">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <LinkIcon className="w-8 h-8 text-primary" />
          </div>
          <h2 className="text-3xl font-bold mb-3">Enter Listing URL</h2>
          <p className="text-muted-foreground text-pretty">
            Paste your Aryeo listing URL below to scrape all available images
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <Input
              type="url"
              placeholder="https://moshin-real-estate-media.aryeo.com/listings/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              className="h-12 text-lg bg-background border-border"
              disabled={loading}
            />
            <p className="text-sm text-muted-foreground mt-2">Must be a valid Aryeo.com listing URL</p>
          </div>

          {error && (
            <div className="flex items-start gap-3 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
              <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-destructive">Error</p>
                <p className="text-sm text-destructive/90">{error}</p>
              </div>
            </div>
          )}

          <Button
            type="submit"
            size="lg"
            className="w-full h-12 text-lg bg-primary hover:bg-primary/90"
            disabled={loading || !url}
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Scraping Images...
              </>
            ) : (
              "Scrape Listing"
            )}
          </Button>
        </form>

        <div className="mt-8 p-4 bg-muted/50 rounded-lg">
          <h3 className="font-semibold mb-2 text-sm">How it works:</h3>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li>• Automatically logs into your Aryeo account</li>
            <li>• Scrapes all high-quality images from the listing</li>
            <li>• Processes images for optimal social media display</li>
          </ul>
        </div>
      </div>
    </Card>
  )
}
