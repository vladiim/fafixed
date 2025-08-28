import { Controller } from "@hotwired/stimulus"

// SPIKE: Simple controller to log refresh button clicks
export default class extends Controller {
  connect() {
    console.log("🎮 SPIKE: Refresh status controller connected to", this.element)
  }
  
  submit(event) {
    const transactionId = this.element.querySelector('input[name="csrfmiddlewaretoken"]')
      ?.closest('form')?.action?.match(/transactions\/(\d+)\/refresh-status/)?.[1]
    
    console.log("🔄 SPIKE: Refresh button clicked for transaction", transactionId)
    console.log("🔄 SPIKE: Form action:", this.element.action)
    console.log("🔄 SPIKE: Form method:", this.element.method)
    console.log("🔄 SPIKE: CSRF token present:", !!this.element.querySelector('input[name="csrfmiddlewaretoken"]'))
    
    const frameTarget = this.element.getAttribute('data-turbo-frame')
    console.log("🔄 SPIKE: Turbo frame target:", frameTarget)
    
    // Check if target frame exists
    const targetFrame = document.getElementById(frameTarget)
    console.log("🔄 SPIKE: Target frame exists:", !!targetFrame)
    console.log("🔄 SPIKE: Target frame element:", targetFrame)
    
    // Check if we're inside the frame
    const currentFrame = this.element.closest('turbo-frame')
    console.log("🔄 SPIKE: Currently inside frame:", currentFrame?.id)
  }
}