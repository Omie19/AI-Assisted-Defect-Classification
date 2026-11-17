import { describe, expect, it } from 'vitest';
import { isOverridden } from './decision';

describe('human confirmation decision', () => {
  it('marks an unchanged AI suggestion as accepted', () => {
    expect(isOverridden('Dent', 'Dent')).toBe(false);
  });

  it('marks a corrected AI suggestion as overridden', () => {
    expect(isOverridden('Dent', 'Paint Issue')).toBe(true);
  });

  it('supports overriding a defect prediction to No Defect', () => {
    expect(isOverridden('Scratch', 'No Defect')).toBe(true);
  });
});
