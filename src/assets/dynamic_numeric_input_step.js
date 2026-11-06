// Numeric inputs with the class `dynamic-step-field` step by the amount in their `step-val-{step}`
// class when the spinner carets or arrow keys are used. The inputs have step="any" (so that any
// value is valid), which makes the browser step by 1; that step is replaced by the custom one.

const MAX_PRECISION = 5;

// The number of decimal places in a number string. Trailing zeros, as in 'step-val-0.100000', do
// not count.
function countDecimals(numStr) {
    const [mantissa, exponent] = numStr.toLowerCase().split('e');
    const fraction = (mantissa.split('.')[1] || '').replace(/0+$/, '');
    return Math.max(0, fraction.length - (parseInt(exponent) || 0));
}

function getStep(input) {
    const stepClass = Array.from(input.classList).find(c => c.startsWith('step-val-'));
    if (!stepClass) return null;
    const stepStr = stepClass.replace('step-val-', '');
    return {
        amount: parseFloat(stepStr) || 1,
        precision: Math.min(countDecimals(stepStr), MAX_PRECISION),
    };
}

// Step from a value string. The result keeps the value's decimals, so a whole-number step moves
// 12.5 to 112.5 rather than rounding it, and is only rounded to remove floating point error.
function stepFrom(valueStr, direction, step) {
    const newValue = (parseFloat(valueStr) || 0) + direction * step.amount;
    return newValue.toFixed(Math.max(step.precision, countDecimals(valueStr || '')));
}

// Set the value so that React (and so Dash) sees the change: assigning `input.value` directly
// would update React's record of the value, and the input event would then be ignored.
const nativeValueSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;

function setValue(input, value) {
    nativeValueSetter.call(input, value);
    input.dataset.lastVal = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
}


// 1. Handle Native Up/Down Caret (Spinner) Clicks
document.addEventListener('input', function(e) {
    const input = e.target.closest('.dynamic-step-field');
    if (!input) return;

    // Typed edits (typing, deleting, pasting, dropping) have an inputType; spinner and mouse
    // wheel changes do not. Events dispatched here are not trusted, and are already stepped.
    if (e.inputType || !e.isTrusted) {
        input.dataset.lastVal = input.value;
        return;
    }

    const step = getStep(input);
    if (!step) return;

    const lastValue = parseFloat(input.dataset.lastVal) || 0;
    const currentValue = parseFloat(input.value) || 0;

    // The browser steps by 1 from the last value
    const diff = currentValue - lastValue;
    if (Math.abs(diff) === 1) {
        setValue(input, stepFrom(input.dataset.lastVal, Math.sign(diff), step));
    } else {
        input.dataset.lastVal = input.value;
    }
});


// 2. Handle Keyboard Arrow Key Presses
document.addEventListener('keydown', function(e) {
    const input = e.target.closest('.dynamic-step-field');
    if (!input) return;

    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        const step = getStep(input);
        if (!step) return;

        // Halt default step="any" keyboard increments
        e.preventDefault();

        setValue(input, stepFrom(input.value, e.key === 'ArrowUp' ? 1 : -1, step));
    }
});


// 3. Start tracking from the value shown when the input is focussed (clicking a spinner focusses
// it), as Dash may have changed the value since the input was last used
document.addEventListener('focusin', function(e) {
    const input = e.target.closest('.dynamic-step-field');
    if (input) {
        input.dataset.lastVal = input.value;
    }
});
