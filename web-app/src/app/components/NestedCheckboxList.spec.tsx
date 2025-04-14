import {
  checkboxCheckValue,
  checkboxIndeterminateValue,
  type CheckboxStructure,
} from './NestedCheckboxList';

const baseCheckbox = (
  overrides: Partial<CheckboxStructure> = {},
): CheckboxStructure => ({
  title: 'Test Checkbox',
  type: 'checkbox',
  checked: false,
  disabled: false,
  children: [],
  ...overrides,
});

describe('checkboxCheckValue', () => {
  it('returns false if checkbox is disabled', () => {
    const checkbox = {
      checked: true,
      disabled: true,
      children: [],
    } as unknown as CheckboxStructure;
    expect(checkboxCheckValue(checkbox, false)).toBe(false);
  });

  it('returns false if disableAll is true', () => {
    const checkbox = {
      checked: true,
      disabled: false,
      children: [],
    } as unknown as CheckboxStructure;
    expect(checkboxCheckValue(checkbox, true)).toBe(false);
  });

  it('returns true if checked is true and not disabled', () => {
    const checkbox = {
      checked: true,
      disabled: false,
      children: [],
    } as unknown as CheckboxStructure;
    expect(checkboxCheckValue(checkbox, false)).toBe(true);
  });

  it('returns true if all children are checked', () => {
    const checkbox = {
      checked: false,
      disabled: false,
      children: [
        { checked: true, disabled: false },
        { checked: true, disabled: false },
      ],
    } as unknown as CheckboxStructure;
    expect(checkboxCheckValue(checkbox, false)).toBe(true);
  });

  it('returns false if any child is not checked', () => {
    const checkbox = {
      checked: false,
      disabled: false,
      children: [
        { checked: true, disabled: false },
        { checked: false, disabled: false },
      ],
    } as unknown as CheckboxStructure;
    expect(checkboxCheckValue(checkbox, false)).toBe(false);
  });
});

describe('checkboxIndeterminateValue', () => {
  it('returns false if disableAll is true', () => {
    const checkbox = baseCheckbox({
      children: [baseCheckbox({ checked: true, disabled: false })],
    });
    expect(checkboxIndeterminateValue(checkbox, true)).toBe(false);
  });

  it('returns false if children is undefined', () => {
    const checkbox = baseCheckbox({
      children: undefined,
    });
    expect(checkboxIndeterminateValue(checkbox, false)).toBe(false);
  });

  it('returns false if all children are checked', () => {
    const checkbox = baseCheckbox({
      children: [
        baseCheckbox({ checked: true, disabled: false }),
        baseCheckbox({ checked: true, disabled: false }),
      ],
    });
    expect(checkboxIndeterminateValue(checkbox, false)).toBe(false);
  });

  it('returns false if no children are checked', () => {
    const checkbox = baseCheckbox({
      children: [
        baseCheckbox({ checked: false, disabled: false }),
        baseCheckbox({ checked: false, disabled: false }),
      ],
    });
    expect(checkboxIndeterminateValue(checkbox, false)).toBe(false);
  });

  it('returns true if some children are checked and some are not', () => {
    const checkbox = baseCheckbox({
      children: [
        baseCheckbox({ checked: true, disabled: false }),
        baseCheckbox({ checked: false, disabled: false }),
      ],
    });
    expect(checkboxIndeterminateValue(checkbox, false)).toBe(true);
  });

  it('returns false if all children are disabled', () => {
    const checkbox = baseCheckbox({
      children: [
        baseCheckbox({ checked: true, disabled: true }),
        baseCheckbox({ checked: false, disabled: true }),
      ],
    });
    expect(checkboxIndeterminateValue(checkbox, false)).toBe(false);
  });

  it('returns true if some children are checked and some are not, and not all children are disabled', () => {
    const checkbox = baseCheckbox({
      children: [
        baseCheckbox({ checked: true, disabled: false }),
        baseCheckbox({ checked: false, disabled: true }),
      ],
    });
    expect(checkboxIndeterminateValue(checkbox, false)).toBe(true);
  });
});
