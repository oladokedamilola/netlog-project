from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import LogUploadForm
from .models import LogUpload

@login_required
def upload_log(request):
    if request.method == "POST":
        form = LogUploadForm(request.POST, request.FILES)
        if form.is_valid():
            log = form.save(commit=False)
            log.user = request.user
            log.save()
            return redirect("upload_history")
    else:
        form = LogUploadForm()

    context = {"form": form}
    return render(request, "logs/upload.html", context)


@login_required
def upload_history(request):
    uploads = LogUpload.objects.filter(user=request.user).order_by("-uploaded_at")
    return render(request, "logs/history.html", {"uploads": uploads})


from .utils.parser_selector import get_parser
from .models import ParsedEntry

@login_required
def process_log(request, upload_id):
    upload = LogUpload.objects.get(id=upload_id, user=request.user)
    file_path = upload.file.path

    parser = get_parser(upload.log_type, file_path)

    for row in parser.parse_file():
        ParsedEntry.objects.create(
            upload=upload,
            ip_address=row["ip"],
            timestamp=row["timestamp"],
            method=row["method"],
            status_code=row["status"],
            url=row["url"],
            user_agent=row["user_agent"],
        )

    return redirect("analysis_dashboard", upload_id=upload.id)
