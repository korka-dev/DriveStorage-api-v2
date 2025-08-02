from datetime import datetime

from mongoengine import Document, StringField, FileField,  DateTimeField, ReferenceField


class Directory(Document):
    dir_name = StringField(required=True)
    owner_id = StringField(required=True)
    created_at = DateTimeField(default=datetime.now())
    owner=StringField(requires=True)

    meta = {"collection": "directories"}


class File(Document):
    file_name = StringField(required=True)
    content_type = StringField(required=True)
    file_content = FileField()
    owner_id = StringField(required=True)
    created_at = DateTimeField(default=datetime.now())
    owner=StringField(requires=True)


    parent = ReferenceField(Directory)

    meta = {"collection": "files"}
