import { Controller } from "@hotwired/stimulus"

// Handles individual suggestion actions (ignore, mark done, fix)
// Works alongside bulk_action_controller for comprehensive suggestion management
export default class extends Controller {
    static targets = ["button"]
    static values = { 
        confirmMessage: String,
        requireConfirmation: { type: Boolean, default: false },
        successMessage: String,
        removeOnSuccess: { type: Boolean, default: true },
        openInNewTab: { type: Boolean, default: false }
    }

    // Handle individual action button clicks
    async performAction(event) {
        event.preventDefault()
        const button = event.target
        const url = button.href || button.dataset.url
        
        if (!url) {
            console.error('No URL found for action')
            return
        }

        // Show confirmation if required
        if (this.requireConfirmationValue) {
            const confirmMessage = this.confirmMessageValue || 'Are you sure?'
            if (!confirm(confirmMessage)) {
                return
            }
        }

        // Store original button state
        const originalText = button.textContent
        const originalDisabled = button.disabled
        
        // Set loading state
        this.setLoadingState(button, true)
        
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'Content-Type': 'application/json',
                },
            })
            
            const data = await response.json()
            
            if (data.success) {
                await this.handleSuccess(data, button)
            } else {
                this.handleError(data.error || 'Action failed', button, originalText, originalDisabled)
            }
            
        } catch (error) {
            this.handleError(`Network error: ${error.message}`, button, originalText, originalDisabled)
        }
    }
    
    // Handle successful action
    async handleSuccess(data, button) {
        // Show success message if configured
        if (this.successMessageValue) {
            this.showMessage(this.successMessageValue, 'success')
        } else if (data.message) {
            this.showMessage(data.message, 'success')
        }
        
        // Handle special actions like opening Xero URL
        if (data.xero_url && this.openInNewTabValue) {
            window.open(data.xero_url, '_blank')
        }
        
        // Remove the suggestion card from DOM if configured
        if (this.removeOnSuccessValue) {
            await this.removeSuggestionCard()
        }
        
        // Dispatch custom event for other controllers to listen to
        this.dispatch('actionSuccess', { 
            detail: { 
                data: data,
                element: this.element 
            } 
        })
    }
    
    // Handle action error
    handleError(errorMessage, button, originalText, originalDisabled) {
        this.showMessage(errorMessage, 'error')
        this.setLoadingState(button, false, originalText, originalDisabled)
    }
    
    // Set button loading state
    setLoadingState(button, isLoading, originalText = null, originalDisabled = false) {
        if (isLoading) {
            button.disabled = true
            button.textContent = 'Processing...'
            button.classList.add('opacity-50', 'cursor-not-allowed')
        } else {
            button.disabled = originalDisabled
            button.textContent = originalText || button.textContent
            button.classList.remove('opacity-50', 'cursor-not-allowed')
        }
    }
    
    // Remove suggestion card with animation
    async removeSuggestionCard() {
        const card = this.element.closest('.suggestion-card') || this.element.closest('[data-suggestion-id]')
        
        if (card) {
            // Animate out
            card.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out'
            card.style.opacity = '0'
            card.style.transform = 'translateX(100px)'
            
            // Wait for animation then remove
            await new Promise(resolve => setTimeout(resolve, 300))
            card.remove()
            
            // Notify bulk action controller if present
            const bulkController = document.querySelector('[data-controller*="bulk-action"]')
            if (bulkController) {
                bulkController.dispatchEvent(new CustomEvent('suggestion:removed'))
            }
        }
    }
    
    // Show user message (can be overridden to use toast notifications)
    showMessage(message, type = 'info') {
        // Simple console logging for now - can be enhanced with toast notifications
        console.log(`${type.toUpperCase()}: ${message}`)
        
        // You could dispatch an event here for a global message controller
        this.dispatch('message', { 
            detail: { 
                message: message, 
                type: type 
            } 
        })
    }
    
    // Get CSRF token from DOM
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                     document.querySelector('meta[name=csrf-token]')?.content
        
        if (!token) {
            console.warn('CSRF token not found')
        }
        
        return token
    }
    
    // Action-specific methods that can be called from templates
    
    async ignore(event) {
        this.requireConfirmationValue = false
        this.successMessageValue = 'Suggestion ignored successfully'
        await this.performAction(event)
    }
    
    async markDone(event) {
        this.requireConfirmationValue = false
        this.successMessageValue = 'Suggestion marked as done'
        await this.performAction(event)
    }
    
    async fix(event) {
        this.requireConfirmationValue = false
        this.successMessageValue = 'Opening Xero to fix categorization'
        this.openInNewTabValue = true
        await this.performAction(event)
    }
}