// 1. Handle Native Up/Down Caret (Spinner) Clicks
document.addEventListener('input', function(e) {
    const input = e.target.closest('.dynamic-step-field');
    if (!input) return;

    // Retrieve the custom step class
    const stepClass = Array.from(input.classList).find(c => c.startsWith('step-val-'));
    if (!stepClass) return;

    const stepStr = stepClass.replace('step-val-', '');
    const stepAmount = parseFloat(stepStr) || 1;

    // Track the last processed manual value using HTML5 dataset
    const lastValue = parseFloat(input.dataset.lastVal) || 0;
    const currentValue = parseFloat(input.value) || 0;

    // If the browser changed the value by exactly 1, a native caret button was clicked
    const diff = currentValue - lastValue;
    if (Math.abs(diff) === 1) {
        let newValue = lastValue;
        
        if (diff > 0) {
            newValue += stepAmount; // Caret Up clicked
        } else {
            newValue -= stepAmount; // Caret Down clicked
        }

        // Apply custom step precision to fix floating-point math issues
        const precision = stepStr.includes('.') ? stepStr.split('.')[1].length : 0;
        input.value = newValue.toFixed(precision);
    }

    // Keep our reference tracking variable up to date
    input.dataset.lastVal = input.value;
});


// 2. Handle Keyboard Arrow Key Presses
document.addEventListener('keydown', function(e) {
    const input = e.target.closest('.dynamic-step-field');
    if (!input) return;

    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        const stepClass = Array.from(input.classList).find(c => c.startsWith('step-val-'));
        if (!stepClass) return;

        const stepStr = stepClass.replace('step-val-', '');
        const stepAmount = parseFloat(stepStr) || 1;

        // Halt default step="any" keyboard increments
        e.preventDefault(); 
        
        let currentValue = parseFloat(input.value) || 0;
        
        if (e.key === 'ArrowUp') {
            currentValue += stepAmount;
        } else if (e.key === 'ArrowDown') {
            currentValue -= stepAmount;
        }

        let precision = stepStr.includes('.') ? stepStr.split('.')[1].length : 0;
        precision = precision > 5 ? 5 : precision;
        input.value = currentValue.toFixed(precision);
        input.dataset.lastVal = input.value;

        // Dispatch input event to notify Dash of layout changes
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }
});


// 3. Initialize tracking variable when a user manually starts typing
document.addEventListener('focusin', function(e) {
    const input = e.target.closest('.dynamic-step-field');
    if (input && !input.dataset.lastVal) {
        input.dataset.lastVal = input.value || 0;
    }
});
