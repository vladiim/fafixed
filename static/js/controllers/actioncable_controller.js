import { Controller } from "@hotwired/stimulus"

/**
 * ActionCable Stimulus Controller
 * 
 * A reusable controller for managing ActionCable WebSocket connections
 * and handling Turbo Stream updates via real-time broadcasts.
 * 
 * Usage:
 * <div data-controller="actioncable" 
 *      data-actioncable-url-value="ws://localhost:8000/cable"
 *      data-actioncable-subscriptions-value='[{"stream_name": "my_stream_1"}, {"stream_name": "my_stream_2"}]'>
 * </div>
 * 
 * Values:
 * - url: WebSocket URL for ActionCable connection
 * - subscriptions: Array of subscription objects with stream_name and optional channel
 * 
 * Methods:
 * - addSubscription(subscription): Add new subscription dynamically
 * - reconnect(): Reconnect the WebSocket
 */
export default class extends Controller {
  static values = { 
    url: String,
    subscriptions: Array
  }

  connect() {
    this.setupWebSocket()
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  setupWebSocket() {
    if (!this.urlValue || !this.subscriptionsValue || this.subscriptionsValue.length === 0) {
      return
    }

    this.ws = new WebSocket(this.urlValue)
    
    this.ws.onopen = () => {
      this.subscriptionsValue.forEach(subscription => {
        const subscriptionMessage = {
          command: 'subscribe',
          identifier: JSON.stringify({
            channel: subscription.channel || 'TurboStreamCableChannel',
            stream_name: subscription.stream_name
          })
        }
        this.ws.send(JSON.stringify(subscriptionMessage))
      })
    }
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        if (data.message) {
          this.handleTurboStream(data.message)
        }
      } catch (e) {
        // ActionCable message parsing error
      }
    }
    
    this.ws.onerror = (error) => {
      // WebSocket connection error
    }

    this.ws.onclose = (event) => {
      // WebSocket connection closed
    }
  }

  handleTurboStream(message) {
    const parser = new DOMParser()
    const doc = parser.parseFromString(message, 'text/html')
    const turboStream = doc.querySelector('turbo-stream')
    
    if (turboStream) {
      document.body.appendChild(turboStream)
    }
  }

  // Public method to add new subscriptions dynamically
  addSubscription(subscription) {
    if (!this.subscriptionsValue) {
      this.subscriptionsValue = []
    }
    
    this.subscriptionsValue.push(subscription)
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const subscriptionMessage = {
        command: 'subscribe',
        identifier: JSON.stringify({
          channel: subscription.channel || 'TurboStreamCableChannel',
          stream_name: subscription.stream_name
        })
      }
      this.ws.send(JSON.stringify(subscriptionMessage))
    }
  }

  // Public method to reconnect WebSocket
  reconnect() {
    this.disconnect()
    this.setupWebSocket()
  }
}