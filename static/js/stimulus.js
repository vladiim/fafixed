console.log("Loading stimulus.js...")

// Load Stimulus and Turbo from node_modules
import { Application } from "@hotwired/stimulus"
import "@hotwired/turbo"
import { createConsumer } from "@rails/actioncable"

console.log("Stimulus and Turbo loaded from node_modules")

// Configure ActionCable consumer for WebSocket connections
console.log("Setting up ActionCable consumer...")
const consumer = createConsumer('ws://localhost:8000/cable')
window.ActionCable = { createConsumer }
window.CableConsumer = consumer

// Debug ActionCable connection using Rails ActionCable API
console.log('ActionCable consumer created:', consumer)

// Monitor connection state
if (consumer.connection) {
  console.log('ActionCable connection object:', consumer.connection)
  
  // Use ActionCable's monitoring API if available
  const originalConnect = consumer.connection.open
  if (originalConnect) {
    consumer.connection.open = function() {
      console.log('ActionCable connecting...')
      const result = originalConnect.apply(this, arguments)
      return result
    }
  }
}

// Import controllers
import AccountDropdownController from "./controllers/account_dropdown_controller.js"
import MessageAlertController from "./controllers/message_alert_controller.js"
import DropdownController from "./controllers/dropdown_controller.js"
import ValidationRunnerController from "./controllers/validation_runner_controller.js"

const application = Application.start()

// Register controllers
application.register("account-dropdown", AccountDropdownController)
application.register("message-alert", MessageAlertController)
application.register("dropdown", DropdownController)
application.register("validation-runner", ValidationRunnerController)

// Configure Stimulus development experience  
application.debug = false  // Disable debug to reduce console noise
window.Stimulus = application

console.log("Stimulus loaded, registered controllers:", application.router.modulesByIdentifier)

// Turbo configuration to prevent message accumulation
document.addEventListener('turbo:before-cache', () => {
  // Remove all message alerts before caching the page
  document.querySelectorAll('[data-controller="message-alert"]').forEach(el => el.remove())
})

// Create subscriptions only when needed (not for all transactions on page load)
// This will be handled by the Turbo Frame updates when validation starts
window.createStreamSubscription = function(streamName) {
  if (!window.CableConsumer || !streamName) {
    console.log('No consumer or stream name available')
    return
  }
  
  // Check if subscription already exists
  const existingSubscription = window.CableConsumer.subscriptions.findAll().find(
    sub => sub.identifier && JSON.parse(sub.identifier).stream_name === streamName
  )
  
  if (existingSubscription) {
    console.log(`Subscription already exists for: ${streamName}`)
    return existingSubscription
  }
  
  console.log(`Creating subscription for: ${streamName}`)
  
  const subscription = window.CableConsumer.subscriptions.create(
    {
      channel: 'TurboStreamCableChannel',
      stream_name: streamName
    },
    {
      connected() {
        console.log(`✅ Connected to stream: ${streamName}`)
      },
      
      disconnected() {
        console.log(`❌ Disconnected from stream: ${streamName}`)
      },
      
      received(data) {
        console.log(`📨 Received data for ${streamName}:`, data)
        
        // Apply turbo stream update
        if (data.type === 'turbo_stream' && data.message) {
          const tempDiv = document.createElement('div')
          tempDiv.innerHTML = data.message
          const turboStream = tempDiv.firstElementChild
          
          if (turboStream && turboStream.tagName === 'TURBO-STREAM') {
            console.log('🔄 Applying Turbo Stream update...')
            document.body.appendChild(turboStream)
          }
        }
      }
    }
  )
  
  return subscription
}

// Debug turbo frame updates and setup subscriptions for validation frames
document.addEventListener('turbo:frame-load', (event) => {
  console.log('Turbo frame loaded:', event.target.id)
  
  // Check for spinner and stream source
  const hasSpinner = event.target.querySelector('.fa-spin')
  const streamSource = event.target.querySelector('turbo-cable-stream-source')
  
  console.log('Frame analysis:', {
    frameId: event.target.id,
    hasSpinner: !!hasSpinner,
    hasStreamSource: !!streamSource,
    streamName: streamSource ? streamSource.getAttribute('stream-name') : null
  })
  
  if (hasSpinner && streamSource) {
    const streamName = streamSource.getAttribute('stream-name')
    console.log(`🔄 Validation running, creating subscription for: ${streamName}`)
    
    // Create subscription for this specific validation
    window.createStreamSubscription(streamName)
  } else if (streamSource) {
    console.log('📋 Stream source found but no validation running, skipping subscription')
  } else {
    console.log('⚪ No stream source in this frame')
  }
})

// Also listen for form submissions to create subscriptions immediately
document.addEventListener('turbo:submit-start', (event) => {
  console.log('Form submission started:', event.target)
  
  // Find the turbo frame that will be updated
  const formFrame = event.target.getAttribute('data-turbo-frame')
  if (formFrame) {
    console.log(`Form will update frame: ${formFrame}`)
    
    // Extract transaction ID from frame name and create subscription preemptively
    const transactionMatch = formFrame.match(/transaction-(\d+)-actions/)
    if (transactionMatch) {
      const transactionId = transactionMatch[1]
      const streamName = `validation_updates_${transactionId}`
      console.log(`🚀 Creating preemptive subscription for: ${streamName}`)
      window.createStreamSubscription(streamName)
    }
  }
})

export { application }