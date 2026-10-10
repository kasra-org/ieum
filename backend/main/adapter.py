from allauth.account.adapter import DefaultAccountAdapter
from main.tasks import send_mail


class CeleryEmailAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        msg = self.render_mail(template_prefix, email, context)
        # Not printed: the body carries verification and password-reset links.
        # After the surrounding transaction commits, as every other send does.
        send_mail.delay_on_commit(msg.subject, msg.body, email)
