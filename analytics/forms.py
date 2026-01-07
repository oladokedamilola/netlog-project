# analytics/forms.py
from django import forms
from django.utils import timezone
from datetime import timedelta

class AnalysisFilterForm(forms.Form):
    DATE_RANGES = [
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('last7', 'Last 7 days'),
        ('last30', 'Last 30 days'),
        ('custom', 'Custom Range'),
    ]
    
    date_range = forms.ChoiceField(
        choices=DATE_RANGES,
        required=False,
        initial='last7',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    status_code = forms.ChoiceField(
        choices=[
            ('', 'All Status Codes'),
            ('2xx', '2xx Success'),
            ('3xx', '3xx Redirection'),
            ('4xx', '4xx Client Errors'),
            ('5xx', '5xx Server Errors'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    ip_address = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by IP address'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if date_range == 'custom' and (not start_date or not end_date):
            raise forms.ValidationError("Please select both start and end dates for custom range")
        
        return cleaned_data