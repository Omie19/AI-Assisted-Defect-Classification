export type DefectType = 'Scratch' | 'Dent' | 'Paint Issue' | 'Missing Component' | 'No Defect';

export function isOverridden(predicted: DefectType, finalDecision: DefectType): boolean {
  return predicted !== finalDecision;
}
