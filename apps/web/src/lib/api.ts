/**
 * Envelope-aware fetch wrapper.
 *
 * All API responses are { success, data | error, details?, request_id }.
 * api<T>() returns the unwrapped data on success, throws ApiError on failure.
 * Cookies (vestrs_access / vestrs_refresh) ride along automatically because
 * we set credentials: "include".
 */

import type { z } from "zod";

import { env } from "@/lib/env";
import {
  type ErrorPayload,
  failureEnvelopeSchema,
  successEnvelopeSchema,
} from "@/lib/schemas/envelope";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, string[]> | undefined;
  readonly requestId: string | null | undefined;

  constructor(
    payload: ErrorPayload,
    status: number,
    details?: Record<string, string[]>,
    requestId?: string | null,
  ) {
    super(payload.message);
    this.name = "ApiError";
    this.code = payload.code;
    this.status = status;
    this.details = details;
    this.requestId = requestId;
  }

  /** Best-effort message for `field`; falls back to the top-level message. */
  fieldMessage(field: string): string | undefined {
    return this.details?.[field]?.[0];
  }
}

export interface RequestOptions {
  signal?: AbortSignal;
  headers?: Record<string, string>;
  body?: unknown;
}

async function request<T extends z.ZodTypeAny>(
  method: string,
  path: string,
  schema: T,
  options: RequestOptions = {},
): Promise<z.infer<T>> {
  const url = `${env.NEXT_PUBLIC_API_URL}${path}`;
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...options.headers,
  };
  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body,
      credentials: "include",
      signal: options.signal,
    });
  } catch {
    // Network error — fabricate a generic envelope-shaped error so callers
    // get a single ApiError type to handle.
    throw new ApiError(
      { code: "NETWORK_ERROR", message: "Network error. Please check your connection." },
      0,
      undefined,
      null,
    );
  }

  // 204 No Content — return undefined as the data.
  if (response.status === 204) {
    return undefined as never;
  }

  let json: unknown;
  try {
    json = await response.json();
  } catch {
    throw new ApiError(
      { code: "INVALID_RESPONSE", message: "Server returned an unexpected response." },
      response.status,
      undefined,
      response.headers.get("x-request-id"),
    );
  }

  if (!response.ok) {
    const failure = failureEnvelopeSchema.safeParse(json);
    if (failure.success) {
      throw new ApiError(
        failure.data.error,
        response.status,
        failure.data.details,
        failure.data.request_id ?? response.headers.get("x-request-id"),
      );
    }
    throw new ApiError(
      { code: "UNKNOWN_ERROR", message: "An unexpected error occurred." },
      response.status,
      undefined,
      response.headers.get("x-request-id"),
    );
  }

  const envelope = successEnvelopeSchema(schema).safeParse(json);
  if (!envelope.success) {
    throw new ApiError(
      { code: "INVALID_RESPONSE", message: "Server returned an unexpected response shape." },
      response.status,
      undefined,
      response.headers.get("x-request-id"),
    );
  }
  return envelope.data.data;
}

export const api = {
  get<T extends z.ZodTypeAny>(path: string, schema: T, options?: RequestOptions) {
    return request("GET", path, schema, options);
  },
  post<T extends z.ZodTypeAny>(path: string, schema: T, options?: RequestOptions) {
    return request("POST", path, schema, options);
  },
  put<T extends z.ZodTypeAny>(path: string, schema: T, options?: RequestOptions) {
    return request("PUT", path, schema, options);
  },
  patch<T extends z.ZodTypeAny>(path: string, schema: T, options?: RequestOptions) {
    return request("PATCH", path, schema, options);
  },
  delete<T extends z.ZodTypeAny>(path: string, schema: T, options?: RequestOptions) {
    return request("DELETE", path, schema, options);
  },
};
