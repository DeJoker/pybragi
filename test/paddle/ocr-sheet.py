import os
from paddlex import create_pipeline
import sys

pipeline = create_pipeline(pipeline="table_recognition_v2")

output = pipeline.predict(
    input=sys.argv[1],
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
)

dir = os.path.dirname(sys.argv[1])

for res in output:
    res.print()
    dir = os.path.join(dir, "outputs")
    res.save_to_html(dir)
    res.save_to_json(dir)