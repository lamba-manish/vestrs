"""HTML+text renderers for transactional email.

Hand-rolled string formatting — no Jinja, no MJML. Premium investor
email is one template; the marginal complexity of a templating engine
isn't worth the dependency. If we add a second template, this becomes
a tiny module of pure functions, not a templating framework.

Design rules baked into the HTML:

* **Table layout**, max-width 600 px — Outlook 2007–2019 doesn't honour
  CSS `max-width` on divs but does on tables.
* **Inline CSS only** — Gmail and several mobile clients strip
  `<style>` blocks. The `<style>` block we keep is for the
  `@media (max-width: 600px)` mobile breakpoint, which Gmail's web
  client *does* preserve when no class is added to the head.
* **No CSS variables, no rgba()** — Outlook desktop ignores both.
* **All colours explicit** — every text node has an inline `color`
  attribute and every cell a `bgcolor` + `background-color`. Apple
  Mail's "auto dark mode" otherwise inverts text-on-light to
  text-on-dark; with explicit colours it leaves us alone.
* **Pre-header text** — first hidden span sets the inbox preview snippet.
* **Bulletproof CTA button** — table-wrapped anchor tag (works in
  Outlook); MSO conditional VML omitted for simplicity, the rounded
  CTA still renders as a sharp-cornered rectangle in Outlook desktop
  which is acceptable.
"""

from __future__ import annotations

from app.adapters.email.base import EmailMessage


def render_welcome_email(*, recipient_email: str, dashboard_url: str) -> EmailMessage:
    subject = "Welcome to Vestrs — your onboarding starts here"
    preheader = (
        "Your private-banking onboarding flow is ready. Five short steps to your first investment."
    )

    html_body = _WELCOME_HTML.replace("{{DASHBOARD_URL}}", _escape(dashboard_url))
    text_body = _WELCOME_TEXT.replace("{{DASHBOARD_URL}}", dashboard_url).replace(
        "{{EMAIL}}", recipient_email
    )

    return EmailMessage(
        to=recipient_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        preheader=preheader,
    )


def _escape(value: str) -> str:
    # Minimal HTML attribute escaping — the only thing we drop into
    # markup is the dashboard URL, which is constructed from settings.
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


# Plain-text fallback. Most modern clients show HTML, but well-built
# transactional senders always include a text/plain alternative —
# improves deliverability score and renders in CLI mail clients.
_WELCOME_TEXT = """\
Welcome to Vestrs.

Your account ({{EMAIL}}) is ready. Five short steps complete your
onboarding:

  1. Profile         — name, nationality, residence, phone
  2. KYC             — identity, liveness, AML screening
  3. Accreditation   — accredited-investor review
  4. Bank link       — masked details only, last four digits stored
  5. First investment

Continue your onboarding:
{{DASHBOARD_URL}}

Every state-changing action is recorded in your audit log, visible
from the dashboard.

—

This is an automated email from Vestrs. Replies aren't monitored. If
you didn't sign up, you can ignore this message — no further action
will be taken.
"""


_WELCOME_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <meta name="x-apple-disable-message-reformatting" />
    <meta name="color-scheme" content="light only" />
    <meta name="supported-color-schemes" content="light only" />
    <title>Welcome to Vestrs</title>
    <style>
      /* Mobile breakpoint — Gmail web preserves head-level @media when
         no class targets are reused inline (which we don't need). */
      @media only screen and (max-width: 600px) {
        .container { width: 100% !important; }
        .stack-pad { padding-left: 24px !important; padding-right: 24px !important; }
        .h1 { font-size: 26px !important; line-height: 32px !important; }
        .body-copy { font-size: 16px !important; line-height: 26px !important; }
        .cta-button { display: block !important; width: 100% !important; }
      }
    </style>
  </head>
  <body
    style="margin:0;padding:0;background-color:#F5F1EA;color:#1A1A1A;
           font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
           -webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;"
    bgcolor="#F5F1EA"
  >
    <!-- Pre-header (hidden, shows in inbox preview line) -->
    <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;
                font-size:1px;line-height:1px;color:#F5F1EA;opacity:0;">
      Your private-banking onboarding flow is ready. Five short steps to your first investment.
    </div>

    <!-- Outer wrapper -->
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"
           width="100%" bgcolor="#F5F1EA"
           style="background-color:#F5F1EA;">
      <tr>
        <td align="center" style="padding:32px 16px;">

          <!-- Container -->
          <table role="presentation" cellpadding="0" cellspacing="0" border="0"
                 class="container" width="600"
                 style="width:600px;max-width:600px;background-color:#FFFFFF;
                        border:1px solid #E6DFD3;border-collapse:separate;
                        border-radius:6px;overflow:hidden;"
                 bgcolor="#FFFFFF">

            <!-- Header -->
            <tr>
              <td class="stack-pad"
                  style="padding:36px 48px 24px 48px;background-color:#FFFFFF;
                         border-bottom:1px solid #EFE8DC;"
                  bgcolor="#FFFFFF">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td align="left">
                      <span style="font-family: Georgia, 'Times New Roman', Times, serif;
                                   font-size:24px;font-weight:700;letter-spacing:0.04em;
                                   color:#1A1A1A;">VESTRS</span>
                    </td>
                    <td align="right"
                        style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                               font-size:11px;letter-spacing:0.16em;text-transform:uppercase;
                               color:#7A7066;">
                      Onboarding
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Hero -->
            <tr>
              <td class="stack-pad"
                  style="padding:40px 48px 8px 48px;background-color:#FFFFFF;"
                  bgcolor="#FFFFFF">
                <p style="margin:0 0 8px 0;
                          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                          font-size:11px;letter-spacing:0.16em;text-transform:uppercase;
                          color:#9C8B5C;">Welcome</p>
                <h1 class="h1" style="margin:0 0 16px 0;
                                       font-family: Georgia, 'Times New Roman', Times, serif;
                                       font-size:32px;line-height:38px;font-weight:400;
                                       color:#1A1A1A;letter-spacing:-0.01em;">
                  Your account is ready.
                </h1>
                <p class="body-copy"
                   style="margin:0 0 16px 0;
                          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                          font-size:15px;line-height:24px;color:#3A3A3A;">
                  Vestrs is a paced, five-step onboarding flow built for
                  high-net-worth investors. Each step writes an audit
                  entry; the entire journey is reviewable from your
                  dashboard.
                </p>
              </td>
            </tr>

            <!-- CTA -->
            <tr>
              <td class="stack-pad"
                  style="padding:8px 48px 32px 48px;background-color:#FFFFFF;"
                  bgcolor="#FFFFFF">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td bgcolor="#1A1A1A"
                        style="background-color:#1A1A1A;border-radius:4px;">
                      <a href="{{DASHBOARD_URL}}"
                         class="cta-button"
                         style="display:inline-block;padding:14px 28px;
                                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                                font-size:14px;font-weight:600;letter-spacing:0.02em;
                                color:#FFFFFF;text-decoration:none;border-radius:4px;">
                        Continue your onboarding &rarr;
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Steps list -->
            <tr>
              <td class="stack-pad"
                  style="padding:0 48px 32px 48px;background-color:#FFFFFF;"
                  bgcolor="#FFFFFF">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="padding:16px 0;border-top:1px solid #EFE8DC;
                               font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                               font-size:14px;line-height:22px;color:#3A3A3A;">
                      <strong style="color:#1A1A1A;">1. Profile</strong>
                      &nbsp;&middot;&nbsp; Name, nationality, residence, phone.
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:16px 0;border-top:1px solid #EFE8DC;
                               font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                               font-size:14px;line-height:22px;color:#3A3A3A;">
                      <strong style="color:#1A1A1A;">2. KYC</strong>
                      &nbsp;&middot;&nbsp; Identity, liveness, and AML screening.
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:16px 0;border-top:1px solid #EFE8DC;
                               font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                               font-size:14px;line-height:22px;color:#3A3A3A;">
                      <strong style="color:#1A1A1A;">3. Accreditation</strong>
                      &nbsp;&middot;&nbsp; Asynchronous accredited-investor review.
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:16px 0;border-top:1px solid #EFE8DC;
                               font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                               font-size:14px;line-height:22px;color:#3A3A3A;">
                      <strong style="color:#1A1A1A;">4. Bank link</strong>
                      &nbsp;&middot;&nbsp; Masked details only — last four digits stored.
                    </td>
                  </tr>
                  <tr>
                    <td style="padding:16px 0;border-top:1px solid #EFE8DC;border-bottom:1px solid #EFE8DC;
                               font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                               font-size:14px;line-height:22px;color:#3A3A3A;">
                      <strong style="color:#1A1A1A;">5. First investment</strong>
                      &nbsp;&middot;&nbsp; Funds routed to a regulated escrow account.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Quiet support note -->
            <tr>
              <td class="stack-pad"
                  style="padding:24px 48px 36px 48px;background-color:#FAF7F2;
                         border-top:1px solid #EFE8DC;"
                  bgcolor="#FAF7F2">
                <p style="margin:0;
                          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                          font-size:13px;line-height:20px;color:#5C5247;">
                  Every state-changing action is written to your audit
                  log inside the same database transaction as the
                  action itself. You can review the full trail from
                  your dashboard at any time.
                </p>
              </td>
            </tr>

          </table>

          <!-- Footer -->
          <table role="presentation" cellpadding="0" cellspacing="0" border="0"
                 class="container" width="600"
                 style="width:600px;max-width:600px;margin-top:24px;">
            <tr>
              <td class="stack-pad" align="center"
                  style="padding:0 48px;
                         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                         font-size:11px;line-height:18px;letter-spacing:0.02em;
                         color:#7A7066;">
                This is an automated email. Replies are not monitored.
                <br />
                If you didn&rsquo;t sign up, you can safely ignore this message.
                <br /><br />
                Vestrs &middot; demonstration onboarding platform
              </td>
            </tr>
          </table>

        </td>
      </tr>
    </table>
  </body>
</html>
"""
