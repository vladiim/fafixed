console.log("Loading stimulus.js...")

// Load Stimulus and Turbo from node_modules
import { Application } from "@hotwired/stimulus"
import "@hotwired/turbo"

console.log("🚀 SPIKE: Stimulus and Turbo loaded, letting Turbo handle WebSocket connections")

// Import controllers
import AccountDropdownController from "./controllers/account_dropdown_controller.js"
import MessageAlertController from "./controllers/message_alert_controller.js"
import DropdownController from "./controllers/dropdown_controller.js"
import ValidationRunnerController from "./controllers/validation_runner_controller.js"
import RefreshStatusController from "./controllers/refresh_status_controller.js"

const application = Application.start()

// Register controllers
application.register("account-dropdown", AccountDropdownController)
application.register("message-alert", MessageAlertController)
application.register("dropdown", DropdownController)
application.register("validation-runner", ValidationRunnerController)
application.register("refresh-status", RefreshStatusController)

// Configure Stimulus development experience  
application.debug = false  // Disable debug to reduce console noise
window.Stimulus = application

console.log("Stimulus loaded, registered controllers:", application.router.modulesByIdentifier)

// SPIKE: Simple Turbo configuration 
document.addEventListener('turbo:before-cache', () => {
  // Remove all message alerts before caching the page
  document.querySelectorAll('[data-controller="message-alert"]').forEach(el => el.remove())
})

// SPIKE: Log Turbo events for debugging
document.addEventListener('turbo:frame-load', (event) => {
  console.log('🔄 SPIKE: Turbo frame loaded:', event.target.id)
})

document.addEventListener('turbo:submit-start', (event) => {
  console.log('🚀 SPIKE: Form submission started for target:', event.target.getAttribute('data-turbo-frame'))
})

document.addEventListener('turbo:submit-end', (event) => {
  console.log('✅ SPIKE: Form submission completed')
  if (event.detail.success) {
    console.log('✅ SPIKE: Form submission successful')
  } else {
    console.log('❌ SPIKE: Form submission failed')
  }
})

// Add error handling
document.addEventListener('turbo:fetch-request-error', (event) => {
  console.log('❌ SPIKE: Turbo fetch request error:', event.detail)
})

document.addEventListener('turbo:frame-missing', (event) => {
  console.log('❌ SPIKE: Turbo frame missing:', event.detail)
})

// SPIKE: Disabled problematic event listeners to focus on core functionality

document.addEventListener('turbo:frame-render', (event) => {
  if (event.target.id.includes('transaction-')) {
    console.log('🖼️ SPIKE: Frame rendered:', event.target.id)
  }
})

document.addEventListener('turbo:frame-load', (event) => {
  if (event.target.id.includes('transaction-')) {
    console.log('📋 SPIKE: Frame loaded:', event.target.id)
  }
})

export { application }