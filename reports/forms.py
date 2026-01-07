# reports/forms.py
from django import forms
from logs.models import LogUpload
from .models import GeneratedReport

class ReportGenerationForm(forms.Form):
    REPORT_TYPES = [
        ('summary', '📊 Summary Report - Overview of key metrics'),
        ('detailed', '📈 Detailed Analysis - In-depth statistics and charts'),
        ('security', '🛡️ Security Report - Security findings and recommendations'),
        ('traffic', '🚦 Traffic Analysis - Traffic patterns and insights'),
    ]
    
    FORMATS = [
        ('pdf', 'PDF Document (Recommended)'),
        ('csv', 'CSV Data Export'),
        ('html', 'HTML Web Page'),
        ('json', 'JSON Data'),
    ]
    
    # Basic information
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Monthly Traffic Report - January 2024'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional description for this report...'
        })
    )
    
    # Report configuration
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.RadioSelect,
        initial='summary'
    )
    
    format = forms.ChoiceField(
        choices=FORMATS,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='pdf'
    )
    
    # Data selection
    upload = forms.ModelChoiceField(
        queryset=LogUpload.objects.none(),  # Will be filtered in __init__
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Select Log File'
    )
    
    # Content options
    include_summary = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Include Executive Summary'
    )
    
    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Include Charts and Graphs'
    )
    
    include_top_data = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Include Top IPs and Endpoints'
    )
    
    include_recommendations = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Include Recommendations'
    )
    
    # Date range filter (optional)
    date_range = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All dates'),
            ('last7', 'Last 7 days'),
            ('last30', 'Last 30 days'),
            ('custom', 'Custom range'),
        ],
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
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter uploads to only show user's uploads
        self.fields['upload'].queryset = LogUpload.objects.filter(user=user)
    
    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if date_range == 'custom':
            if not start_date or not end_date:
                raise forms.ValidationError("Please select both start and end dates for custom range")
            if start_date > end_date:
                raise forms.ValidationError("Start date must be before end date")
        
        return cleaned_data

class QuickReportForm(forms.Form):
    """Form for quick one-click report generation"""
    upload = forms.ModelChoiceField(
        queryset=LogUpload.objects.none(),
        widget=forms.HiddenInput()
    )
    
    format = forms.ChoiceField(
        choices=[
            ('pdf', 'PDF'),
            ('csv', 'CSV'),
        ],
        initial='pdf',
        widget=forms.HiddenInput()
    )