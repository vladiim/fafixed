import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["container", "conditionsInput"]
  
  static values = { 
    operators: Array,
    fields: Array
  }
  
  connect() {
    this.conditionIndex = 0
    this.updateDisplay()
  }
  
  addCondition() {
    const conditionHtml = this.buildConditionHtml(this.conditionIndex++)
    
    // Replace empty state or add new condition
    if (this.containerTarget.querySelector('.bg-gray-50')) {
      this.containerTarget.innerHTML = conditionHtml
    } else {
      this.containerTarget.insertAdjacentHTML('beforeend', conditionHtml)
    }
    
    this.updateConditionsInput()
  }
  
  removeCondition(event) {
    event.preventDefault()
    const conditionElement = event.target.closest('[data-condition-index]')
    conditionElement.remove()
    
    // Show empty state if no conditions left
    if (!this.containerTarget.querySelector('[data-condition-index]')) {
      this.showEmptyState()
    }
    
    this.updateConditionsInput()
  }
  
  updateConditionsInput() {
    const conditions = []
    const conditionElements = this.containerTarget.querySelectorAll('[data-condition-index]')
    
    conditionElements.forEach((element, index) => {
      const field = element.querySelector('[data-field="field"]')?.value
      const operator = element.querySelector('[data-field="operator"]')?.value
      const value = element.querySelector('[data-field="value"]')?.value
      
      if (field && operator && value) {
        conditions.push({ field, operator, value })
      }
    })
    
    // Update hidden input with JSON conditions
    if (this.hasConditionsInputTarget) {
      this.conditionsInputTarget.value = JSON.stringify(conditions)
    }
  }
  
  buildConditionHtml(index) {
    const fieldOptions = this.fieldsValue.map(field => 
      `<option value="${field.value}">${field.label}</option>`
    ).join('')
    
    const operatorOptions = this.operatorsValue.map(op => 
      `<option value="${op.value}">${op.label}</option>`
    ).join('')
    
    return `
      <div class="border border-gray-200 rounded-lg p-4 mb-4" data-condition-index="${index}">
        <div class="flex items-center justify-between mb-4">
          <span class="text-sm font-medium text-gray-700">Condition ${index + 1}</span>
          <button type="button" 
                  data-action="click->rule-conditions#removeCondition"
                  class="text-red-500 hover:text-red-700">
            <i class="fas fa-trash text-sm"></i>
          </button>
        </div>
        
        <div class="grid grid-cols-3 gap-4">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Field</label>
            <select data-field="field" 
                    data-action="change->rule-conditions#updateConditionsInput"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green text-sm">
              <option value="">Select field...</option>
              ${fieldOptions}
            </select>
          </div>
          
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Operator</label>
            <select data-field="operator"
                    data-action="change->rule-conditions#updateConditionsInput"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green text-sm">
              <option value="">Select operator...</option>
              ${operatorOptions}
            </select>
          </div>
          
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Value</label>
            <input type="text" 
                   data-field="value"
                   data-action="input->rule-conditions#updateConditionsInput"
                   placeholder="Enter value..."
                   class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green text-sm">
          </div>
        </div>
      </div>
    `
  }
  
  showEmptyState() {
    this.containerTarget.innerHTML = `
      <div class="bg-gray-50 rounded-lg p-4">
        <div class="text-center text-gray-500 py-8">
          <i class="fas fa-plus-circle text-2xl mb-2"></i>
          <p class="text-sm">Click "Add Condition" to create your first condition</p>
        </div>
      </div>
    `
  }
  
  updateDisplay() {
    // Update condition count display if needed
    const count = this.containerTarget.querySelectorAll('[data-condition-index]').length
    this.dispatch("conditionCountChanged", { detail: { count } })
  }
}