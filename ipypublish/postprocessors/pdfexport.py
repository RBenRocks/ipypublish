#!/usr/bin/env python
""" a module for exporting latex file to pdf
TODO could this be refactored as nbconvert postprocessor
"""
import logging
import os
import shutil
import tempfile
from subprocess import Popen, PIPE, STDOUT
import webbrowser

from traitlets import Bool, Unicode

from ipypublish.postprocessors.base import IPyPostProcessor

logger = logging.getLogger("pdfexport")


class PDFExport(IPyPostProcessor):
    """ a post processor to convert tex to pdf using latexmk
    """
    @property
    def allowed_mimetypes(self):
        return ("text/latex")

    @property
    def requires_file(self):
        return True

    files_folder = Unicode(
        None, allow_none=True,
        help="the path (relative to the main file path) of external files"
    ).tag(config=True)

    convert_in_temp = Bool(
        False,
        help="run conversion in a temporary directory, "
        "and copy back only PDF file"
    ).tag(config=True)

    debug_mode = Bool(
        False,
        help="run in debug mode").tag(config=True)

    open_in_browser = Bool(
        False,
        help="launch a html page containing a pdf browser").tag(config=True)

    def run_postprocess(self, stream, filepath):
        """ should not be called directly

        Parameters
        ----------
        stream: str
            the main file contents
        filepath: None or pathlib.Path
            the path to the output file

        Returns
        -------
        stream: str
        filepath: None or pathlib.Path

        """
        logger.info('running pdf conversion')
        self._export_pdf(filepath)
        return stream, filepath

    def _export_pdf(self, texpath):

        texname = os.path.splitext(texpath.name)[0]
        # TODO outdir was originally passed, but would this ever be different
        # to the texpath's parent

        if self.files_folder is not None:
            abs_files_path = texpath.parent.joinpath(self.files_folder)
            logger.info(abs_files_path)
            if not abs_files_path.exists():
                self.handle_error(
                    'the external folder path does not exist: {}'.format(
                        abs_files_path), IOError, logger)
            if not abs_files_path.is_dir():
                self.handle_error(
                    'the external folder path is not a directory: {}'.format(
                        abs_files_path), IOError, logger)
        else:
            abs_files_path = None

        self.check_exe_exists(
            'latexmk', logger,
            'requires the latexmk executable to run. '
            'See http://mg.readthedocs.io/latexmk.html#installation',
        )

        if self.convert_in_temp:
            out_folder = tempfile.mkdtemp()
            try:
                exitcode = self._run_latexmk(
                    texpath, out_folder, abs_files_path)
                if exitcode == 0:
                    shutil.copyfile(
                        os.path.join(out_folder, texname + '.pdf'),
                        str(texpath.parent.joinpath(texname + '.pdf')))
            finally:
                shutil.rmtree(out_folder)
        else:
            exitcode = self._run_latexmk(
                texpath, str(texpath.parent), abs_files_path)

        if exitcode == 0:
            logger.info('pdf conversion complete')

            view_pdf = VIEW_PDF.format(
                pdf_name=texname.replace(' ', '%20') + '.pdf')
            view_pdf_path = texpath.parent.joinpath(texname + '.view_pdf.html')
            with view_pdf_path.open('w', encoding='utf-8') as fobj:
                fobj.write(view_pdf)
        else:
            self.handle_error(
                'pdf conversion failed: '
                'Try running with pdf-debug flag',
                RuntimeError, logger)

        if self.open_in_browser:
            #  2 opens the url in a new tab
            webbrowser.open(view_pdf_path.as_uri(), new=2)

        return

    def _run_latexmk(self, texpath, out_folder, abs_files_path):
        """ run latexmk conversion
        """
        # make sure tex file in right place
        outpath = os.path.join(out_folder, texpath.name)
        if os.path.dirname(str(texpath)) != str(out_folder):
            logger.debug('copying tex file to: {}'.format(
                os.path.join(str(out_folder), texpath.name)))
            shutil.copyfile(str(texpath), os.path.join(
                str(out_folder), texpath.name))

        # make sure the external files folder is in right place
        if abs_files_path is not None:
            logger.debug('external files folder set')
            outfilespath = os.path.join(out_folder, str(abs_files_path.name))
            if str(abs_files_path) != str(outfilespath):
                logger.debug(
                    'copying external files to: {}'.format(outfilespath))
                if os.path.exists(outfilespath):
                    shutil.rmtree(outfilespath)
                shutil.copytree(str(abs_files_path), str(outfilespath))

        # run latexmk in correct folder
        with change_dir(out_folder):
            latexmk = ['latexmk', '-xelatex', '-bibtex', '-pdf']
            latexmk += [] if self.debug_mode else ["--interaction=batchmode"]
            logger.info('running: ' + ' '.join(latexmk + ['<outpath>']))
            latexmk += [outpath]

            def log_latexmk_output(pipe):
                for line in iter(pipe.readline, b''):
                    logger.info('latexmk: {}'.format(
                        line.decode("utf-8").strip()))

            process = Popen(latexmk, stdout=PIPE, stderr=STDOUT)
            with process.stdout:
                log_latexmk_output(process.stdout)
            exitcode = process.wait()  # 0 means success

        return exitcode


class change_dir:
    """Context manager for changing the current working directory"""

    def __init__(self, new_path):
        self.newPath = os.path.expanduser(new_path)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


VIEW_PDF = r"""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">

<head>
    <meta http-equiv="content-type" content="text/html; charset=windows-1252">
    <title>View PDF</title>

    <script type="text/javascript">
       var filepath = "{pdf_name}";
       var timer = null;

       function refresh(){{
          var d = document.getElementById("pdf"); // gets pdf-div
          d.innerHTML = '<iframe style="position: absolute; height: 100%; border: none" id="ipdf" src='+window.filepath+'  width="100%"></iframe>';
       }}

       function autoRefresh(){{
          timer = setTimeout("autoRefresh()", 20000);
          refresh();
       }}

       function manualRefresh(){{
          clearTimeout(timer);
          refresh();
       }}
       function check_pdf() {{
         var newfile = document.f.userFile.value;
         ext = newfile.substring(newfile.length-3,newfile.length);
         ext = ext.toLowerCase();
         if(ext != 'pdf') {{
           alert('You selected a .'+ext+
                 ' file; please select a .pdf file instead!'+filepath);
           return false; }}
         else
             alert(newfile);
             window.filepath = newfile;
             alert(filepath);
             refresh();
           return true; }}
    </script>

</head>
<body>
    <!-- <form name=f onsubmit="return check_pdf();"
        action='' method='POST' enctype='multipart/form-data'>
        <input type='submit' name='upload_btn' value='upload'>
        <input type='file' name='userFile' accept="application/pdf">
    </form> -->
    <button onclick="manualRefresh()">manual refresh</button>
    <button onclick="autoRefresh()">auto refresh</button>
    <div id="pdf"></div>
</body>
<script type="text/javascript">refresh();</script>
</html>
"""
