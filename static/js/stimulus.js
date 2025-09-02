// Load Stimulus, Turbo, and ActionCable from node_modules
import { Application } from "@hotwired/stimulus"
import "@hotwired/turbo"
import { createConsumer } from "@rails/actioncable"

// Get WebSocket URL from meta tag (set in base.html from Django settings)
const websocketMeta = document.querySelector('meta[name="websocket-url"]')
const websocketUrl = websocketMeta ? websocketMeta.content : "ws://localhost:8000/cable"

// Configure ActionCable to connect to our WebSocket endpoint
const cable = createConsumer(websocketUrl)
window.cable = cable  // Make it globally available

// Add ActionCable connection debugging with correct API
cable.subscriptions.consumer.events = {
  connected() {},
  disconnected() {},
  rejected() {}
}

// Import controllers
import AccountDropdownController from "./controllers/account_dropdown_controller.js"
import MessageAlertController from "./controllers/message_alert_controller.js"
import DropdownController from "./controllers/dropdown_controller.js"
import ValidationRunnerController from "./controllers/validation_runner_controller.js"
import RefreshStatusController from "./controllers/refresh_status_controller.js"
import ActionCableController from "./controllers/actioncable_controller.js"
import BulkActionController from "./controllers/bulk_action_controller.js"

const application = Application.start()

// Register controllers
application.register("account-dropdown", AccountDropdownController)
application.register("message-alert", MessageAlertController)
application.register("dropdown", DropdownController)
application.register("validation-runner", ValidationRunnerController)
application.register("refresh-status", RefreshStatusController)
application.register("actioncable", ActionCableController)
application.register("bulk-action", BulkActionController)

// Configure Stimulus development experience  
application.debug = false  // Disable debug to reduce console noise
window.Stimulus = application

// Simple Turbo configuration 
document.addEventListener('turbo:before-cache', () => {
  // Remove all message alerts before caching the page
  document.querySelectorAll('[data-controller="message-alert"]').forEach(el => el.remove())
})

// Error handling for Turbo
document.addEventListener('turbo:fetch-request-error', (event) => {
  // Turbo fetch error handled
})

document.addEventListener('turbo:frame-missing', (event) => {
  // Turbo frame missing handled
})


export { application }