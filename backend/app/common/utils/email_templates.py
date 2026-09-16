"""
HTML bodies for the transactional emails sent via app.common.utils.mailer.
Each function returns (subject, html_body) so callers just do:

    subject, body = otp_verification_email(...)
    send_email(to=student.email, subject=subject, body=body, html=True)

One shared `_wrap` gives every email the same LearnIn header/footer chrome
(colors match app/static/css/variables.css) rather than each template
reinventing the layout.
"""

_NAVY = "#1E3A5F"
_AMBER = "#FFC107"
_TEXT = "#111827"
_TEXT_MUTED = "#6b7280"


def _wrap(preview_text: str, body_html: str) -> str:
    return f"""\
<!doctype html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">
  <span style="display:none;font-size:0;color:#f3f4f6;">{preview_text}</span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:8px;overflow:hidden;max-width:480px;width:100%;">
          <tr>
            <td style="background:{_NAVY};padding:20px 32px;">
              <span style="color:#ffffff;font-size:20px;font-weight:bold;">LearnIn</span>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;color:{_TEXT};font-size:15px;line-height:1.6;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:16px 32px;background:#f9fafb;color:{_TEXT_MUTED};font-size:12px;">
              This is an automated message from LearnIn. If you didn't expect this email, you can ignore it.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def otp_verification_email(full_name: str | None, otp_code: str, expires_in_minutes: int) -> tuple[str, str]:
    greeting = f"Hi {full_name}," if full_name else "Hi,"

    body = f"""\
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 24px;">Use the code below to verify your email address and finish setting up your LearnIn account.</p>
    <p style="margin:0 0 24px;text-align:center;">
      <span style="display:inline-block;background:{_AMBER};color:{_NAVY};font-size:28px;font-weight:bold;
                   letter-spacing:6px;padding:12px 24px;border-radius:6px;">{otp_code}</span>
    </p>
    <p style="margin:0;color:{_TEXT_MUTED};">This code expires in {expires_in_minutes} minutes. If you didn't create a LearnIn account, you can ignore this email.</p>
    """

    return "Verify your email - LearnIn", _wrap(f"Your LearnIn verification code is {otp_code}", body)


def institution_request_confirmation_email(institution_name: str, contact_name: str | None) -> tuple[str, str]:
    greeting = f"Hi {contact_name}," if contact_name else "Hi,"

    body = f"""\
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">
      We've received your request to register <strong>{institution_name}</strong> on LearnIn.
    </p>
    <p style="margin:0 0 16px;">
      Our team will review the details and get back to you shortly. You'll receive another email as soon
      as a decision is made - there's nothing further you need to do right now.
    </p>
    <p style="margin:0;color:{_TEXT_MUTED};">Thanks for choosing LearnIn.</p>
    """

    return (
        f"We've received your request for {institution_name} - LearnIn",
        _wrap(f"Your LearnIn registration request for {institution_name} was received", body),
    )


def institution_status_update_email(
    institution_name: str,
    contact_name: str | None,
    approved: bool,
) -> tuple[str, str]:
    greeting = f"Hi {contact_name}," if contact_name else "Hi,"

    if approved:
        subject = "Your institution has been approved - LearnIn"
        message = (
            f"Good news - <strong>{institution_name}</strong> has been approved. "
            "You can now log in and start using LearnIn."
        )
        cta_label, cta_color = "Log in", _AMBER
    else:
        subject = f"Update on your LearnIn registration for {institution_name}"
        message = (
            f"<strong>{institution_name}</strong> has been deactivated on LearnIn. "
            "If you believe this is a mistake, please reach out to our support team."
        )
        cta_label, cta_color = None, None

    cta_html = ""
    if cta_label:
        cta_html = f"""
        <p style="margin:24px 0 0;text-align:center;">
          <a href="/institution/login" style="display:inline-block;background:{cta_color};color:{_NAVY};
             font-weight:bold;text-decoration:none;padding:12px 24px;border-radius:6px;">{cta_label}</a>
        </p>
        """

    body = f"""\
    <p style="margin:0 0 16px;">{greeting}</p>
    <p style="margin:0 0 16px;">{message}</p>
    {cta_html}
    """

    preview_text = (
        f"{institution_name} has been approved on LearnIn"
        if approved
        else f"An update on your LearnIn registration for {institution_name}"
    )

    return subject, _wrap(preview_text, body)
