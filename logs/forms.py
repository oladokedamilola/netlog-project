from django import forms
from .models import LogUpload

class LogUploadForm(forms.ModelForm):
    class Meta:
        model = LogUpload
        fields = ["log_type", "file"]
        widgets = {
            "log_type": forms.Select(attrs={"class": "form-select"}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }

    def clean_file(self):
        file = self.cleaned_data.get("file")

        if file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("File size must not exceed 5MB.")

        allowed_extensions = ["log", "txt"]
        ext = file.name.split(".")[-1].lower()

        if ext not in allowed_extensions:
            raise forms.ValidationError("Only .log or .txt files are allowed.")

        return file
