from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
import os
from .models import GeneratedReport, ReportTemplate

@receiver(post_delete, sender=GeneratedReport)
def delete_report_file(sender, instance, **kwargs):
    """
    Delete the physical report file when the database record is deleted
    This ensures no orphaned files are left in storage
    """
    if instance.file:
        # Check if file exists before deleting
        if os.path.isfile(instance.file.path):
            try:
                os.remove(instance.file.path)
            except (OSError, IOError) as e:
                # Log error but don't crash
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error deleting report file {instance.file.path}: {str(e)}")

@receiver(pre_save, sender=ReportTemplate)
def set_default_template(sender, instance, **kwargs):
    """
    Ensure only one template is marked as default per template_type
    When a template is set as default, unset other defaults of same type
    """
    if instance.is_default:
        # Find other templates of same type that are marked as default
        same_type_defaults = ReportTemplate.objects.filter(
            template_type=instance.template_type,
            is_default=True
        ).exclude(id=instance.id)  # Exclude current instance if updating
        
        # Unset their default flag
        same_type_defaults.update(is_default=False)

@receiver(pre_save, sender=GeneratedReport)
def update_file_size(sender, instance, **kwargs):
    """
    Update file_size field when file is changed
    """
    if instance.file and instance.file.size:
        instance.file_size = instance.file.size