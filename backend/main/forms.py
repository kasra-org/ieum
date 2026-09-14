from django import forms
from .models import User, Institution

class CustomSignupForm(forms.ModelForm):
    institute = forms.ModelChoiceField(
        queryset=Institution.objects.all(),
        required=False,
        to_field_name='id'
    )
    # Present when the person arrived through an event invitation link: the
    # signup then registers them for that event as well - see main.invitations.
    invitation_token = forms.CharField(required=False, max_length=64)

    class Meta:
        model = User
        fields = [
            'first_name',
            'middle_initial',
            'last_name',
            'nationality',
            'job_title',
            'institute',
            'department',
            'disability',
            'dietary',
        ]

    def signup(self, request, user):
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.middle_initial = self.cleaned_data['middle_initial']
        user.last_name = self.cleaned_data['last_name']
        user.nationality = self.cleaned_data['nationality']
        user.job_title = self.cleaned_data['job_title']
        user.institute = self.cleaned_data['institute']
        user.department = self.cleaned_data['department']
        user.disability = self.cleaned_data['disability']
        user.dietary = self.cleaned_data['dietary']
        user.save()

        # After save, so the attendee copies a persisted profile. Best effort:
        # a stale or mismatched invitation must not cost them the account.
        from main import invitations
        invitations.accept_by_token(self.cleaned_data.get('invitation_token'), user)
        return user