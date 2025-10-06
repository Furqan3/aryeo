"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Label } from "@/components/ui/label"

interface StepThreeProps {
  onComplete: () => void
  onBack: () => void
}

export function StepThree({ onComplete, onBack }: StepThreeProps) {
  const [formData, setFormData] = useState({
    price: "",
    bedrooms: "",
    bathrooms: "",
    square_feet: "",
    address: "",
    city: "",
    state: "",
    zip_code: "",
    property_type: "Single Family Home",
    year_built: "",
    lot_size: "",
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Store form data in sessionStorage for next step
    sessionStorage.setItem("propertyInfo", JSON.stringify(formData))
    onComplete()
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  return (
    <Card className="p-8 gradient-card border-border">
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-3">Property Details</h2>
        <p className="text-muted-foreground">Enter the property information to generate your social media post</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid md:grid-cols-2 gap-6">
          {/* Price */}
          <div>
            <Label htmlFor="price">Price *</Label>
            <Input
              id="price"
              name="price"
              placeholder="$500,000"
              value={formData.price}
              onChange={handleChange}
              required
              className="mt-1.5 bg-background"
            />
          </div>

          {/* Bedrooms */}
          <div>
            <Label htmlFor="bedrooms">Bedrooms *</Label>
            <Input
              id="bedrooms"
              name="bedrooms"
              type="number"
              min="0"
              placeholder="3"
              value={formData.bedrooms}
              onChange={handleChange}
              required
              className="mt-1.5 bg-background"
            />
          </div>

          {/* Bathrooms */}
          <div>
            <Label htmlFor="bathrooms">Bathrooms *</Label>
            <Input
              id="bathrooms"
              name="bathrooms"
              type="number"
              step="0.5"
              min="0"
              placeholder="2.5"
              value={formData.bathrooms}
              onChange={handleChange}
              required
              className="mt-1.5 bg-background"
            />
          </div>

          {/* Square Feet */}
          <div>
            <Label htmlFor="square_feet">Square Feet *</Label>
            <Input
              id="square_feet"
              name="square_feet"
              type="number"
              min="100"
              placeholder="2500"
              value={formData.square_feet}
              onChange={handleChange}
              required
              className="mt-1.5 bg-background"
            />
          </div>

          {/* Address */}
          <div className="md:col-span-2">
            <Label htmlFor="address">Street Address *</Label>
            <Input
              id="address"
              name="address"
              placeholder="123 Main Street"
              value={formData.address}
              onChange={handleChange}
              required
              className="mt-1.5 bg-background"
            />
          </div>

          {/* City */}
          <div>
            <Label htmlFor="city">City *</Label>
            <Input
              id="city"
              name="city"
              placeholder="Los Angeles"
              value={formData.city}
              onChange={handleChange}
              required
              className="mt-1.5 bg-background"
            />
          </div>

          {/* State */}
          <div>
            <Label htmlFor="state">State *</Label>
            <Input
              id="state"
              name="state"
              placeholder="CA"
              maxLength={2}
              value={formData.state}
              onChange={handleChange}
              required
              className="mt-1.5 bg-background"
            />
          </div>

          {/* Zip Code */}
          <div>
            <Label htmlFor="zip_code">Zip Code *</Label>
            <Input
              id="zip_code"
              name="zip_code"
              placeholder="90210"
              value={formData.zip_code}
              onChange={handleChange}
              required
              className="mt-1.5 bg-background"
            />
          </div>

          {/* Property Type */}
          <div>
            <Label htmlFor="property_type">Property Type</Label>
            <select
              id="property_type"
              name="property_type"
              value={formData.property_type}
              onChange={handleChange}
              className="mt-1.5 w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
            >
              <option>Single Family Home</option>
              <option>Condo</option>
              <option>Townhouse</option>
              <option>Multi-Family</option>
              <option>Land</option>
              <option>Commercial</option>
            </select>
          </div>

          {/* Year Built */}
          <div>
            <Label htmlFor="year_built">Year Built</Label>
            <Input
              id="year_built"
              name="year_built"
              type="number"
              min="1800"
              max={new Date().getFullYear()}
              placeholder="2020"
              value={formData.year_built}
              onChange={handleChange}
              className="mt-1.5 bg-background"
            />
          </div>

          {/* Lot Size */}
          <div>
            <Label htmlFor="lot_size">Lot Size</Label>
            <Input
              id="lot_size"
              name="lot_size"
              placeholder="0.25 acres"
              value={formData.lot_size}
              onChange={handleChange}
              className="mt-1.5 bg-background"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-4 pt-4">
          <Button type="button" variant="outline" onClick={onBack} size="lg" className="flex-1 bg-transparent">
            Back
          </Button>
          <Button type="submit" size="lg" className="flex-1 bg-primary hover:bg-primary/90">
            Generate Post
          </Button>
        </div>
      </form>
    </Card>
  )
}
