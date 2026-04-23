import { ApiError } from '@/api/client'

/**
 * Matches the 403 body returned by `require_second_factor` on the server
 * whenever a TOTP-enabled user hits a gated action without a fresh code.
 */
export function isTotpChallengeError(error: unknown): error is ApiError {
  if (!(error instanceof ApiError) || error.status !== 403) return false
  const body = error.body
  if (!body || typeof body !== 'object') return false
  const detail = 'detail' in body ? (body as { detail?: unknown }).detail : null
  if (!detail || typeof detail !== 'object') return false
  const code = 'error' in detail ? (detail as { error?: unknown }).error : null
  return code === 'totp_required' || code === 'totp_invalid'
}
