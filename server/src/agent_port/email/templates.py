def verification_email(verify_url: str, code: str) -> str:
    return f"""\
<div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
  <h2 style="font-size: 18px;">Verify your email</h2>
  <p style="font-size: 14px; color: #444;">
    Enter this verification code in AgentPort:
  </p>
  <p
    style="margin: 16px 0; padding: 14px 18px; background: #f5f5f5; border-radius: 8px;
           font-size: 28px; font-weight: 700; letter-spacing: 0.28em; text-align: center;"
  >
    {code}
  </p>
  <p style="font-size: 14px; color: #444;">
    You can also verify your email by clicking the link below:
  </p>
  <p>
    <a href="{verify_url}"
       style="display: inline-block; padding: 10px 20px; background: #111; color: #fff;
              text-decoration: none; border-radius: 6px; font-size: 14px;">
      Verify email
    </a>
  </p>
  <p style="font-size: 12px; color: #888;">
    The code expires in 30 minutes. You can request a new email every 10 minutes.
  </p>
  <p style="font-size: 12px; color: #888;">
    If you didn't create an account, you can ignore this email.
  </p>
</div>"""


def password_reset_email(reset_url: str) -> str:
    return f"""\
<div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
  <h2 style="font-size: 18px;">Reset your password</h2>
  <p style="font-size: 14px; color: #444;">
    Click the link below to reset your password. This link expires in 1 hour.
  </p>
  <p>
    <a href="{reset_url}"
       style="display: inline-block; padding: 10px 20px; background: #111; color: #fff;
              text-decoration: none; border-radius: 6px; font-size: 14px;">
      Reset password
    </a>
  </p>
  <p style="font-size: 12px; color: #888;">
    If you didn't request a password reset, you can ignore this email.
  </p>
</div>"""
