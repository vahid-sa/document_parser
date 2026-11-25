import io
from docling.datamodel.base_models import InputFormat
from docling.datamodel.base_models import DocumentStream
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from .base_converter import BaseConverter


class PDFConverter(BaseConverter):
    def __init__(self):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True
        self.__converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )
        super().__init__()

    def convert_to_markdown(self, content, page_number: int):
        stream = DocumentStream(
            name="document.pdf",
            stream=io.BytesIO(content)
        )
        n = page_number + 1 
        result = self.__converter.convert(stream, page_range=(n, n))
        markdown = result.document.export_to_markdown()
        return markdown
