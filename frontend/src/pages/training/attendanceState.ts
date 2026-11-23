/** Ignore responses belonging to an effect that has already been cleaned up. */
export function loadCurrent<T>(request: () => Promise<T>, success: (value: T) => void,
  failure: (error: unknown) => void, complete: () => void = () => {}) {
  let current = true
  void request().then(value => { if (current) success(value) })
    .catch(error => { if (current) failure(error) })
    .finally(() => { if (current) complete() })
  return () => { current = false }
}

export function mayLeaveAttendance(dirty: boolean, confirm: () => boolean) {
  return !dirty || confirm()
}
