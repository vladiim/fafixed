import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { delay: Number }
  
  connect() {
    // Add fade-in animation
    this.element.classList.add('alert-fade-in')
    
    // Auto-dismiss after delay
    if (this.delayValue > 0) {
      this.timeoutId = setTimeout(() => {
        this.dismiss()
      }, this.delayValue)
    }
  }
  
  disconnect() {
    if (this.timeoutId) {
      clearTimeout(this.timeoutId)
    }
  }
  
  dismiss() {
    // Add fade-out animation
    this.element.classList.add('alert-fade-out')
    
    // Remove element after animation
    setTimeout(() => {
      this.element.remove()
    }, 300)
  }
}