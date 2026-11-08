export class ApiError extends Error {
  constructor(message, { status = null, detail = null, kind = "api" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.kind = kind;
  }
}

async function readResponseBody(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  try {
    const text = await response.text();
    return text ? { detail: text } : null;
  } catch {
    return null;
  }
}

function getErrorDetail(body) {
  if (!body) {
    return "";
  }
  if (typeof body === "string") {
    return body;
  }
  if (typeof body.detail === "string") {
    return body.detail;
  }
  if (typeof body.message === "string") {
    return body.message;
  }
  return "";
}

export async function requestJson(
  url,
  options = {},
  {
    defaultMessage = "Request failed.",
    timeoutMessage = "The request timed out. Try again.",
    networkMessage =
      "Unable to reach the server. Check that the stack is running.",
    timeoutMs = 15000,
  } = {}
) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });

    const body = await readResponseBody(response);
    if (!response.ok) {
      const detail = getErrorDetail(body);
      throw new ApiError(detail || defaultMessage, {
        status: response.status,
        detail,
        kind: "http",
      });
    }

    if (response.status === 204) {
      return null;
    }

    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new ApiError("Received an unexpected response from the server.", {
        kind: "parse",
      });
    }

    if (body == null) {
      throw new ApiError("Received an empty response from the server.", {
        kind: "parse",
      });
    }

    return body;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error?.name === "AbortError") {
      throw new ApiError(timeoutMessage, { kind: "timeout" });
    }

    throw new ApiError(networkMessage, { kind: "network" });
  } finally {
    window.clearTimeout(timeoutId);
  }
}