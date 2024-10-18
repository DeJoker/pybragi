
from io import BufferedReader


class TailNLog():
    def __init__(self, logfile='', tail=100, total_lines=3000, **kwargs):
        self.logfile = logfile
        self.tail = tail
        self.total_lines = total_lines
        self.current_pos = None
        self.io = None
        self.stop_reading = False
        self.last_data = ""

        self.load_logfile()

        # kwargs.pop("value", None)
        # super().__init__(value=self.read_to_end, **kwargs)

    def read_to_end(self) -> str:
        if self.current_pos is None or self.stop_reading:
            return None
        self.io.seek(self.current_pos)
        b = self.io.read().decode()
        self.current_pos = self.io.tell()
        if b:
            self.last_data += b
            lines = self.last_data.splitlines()
            if len(lines) > self.total_lines:
                lines = lines[-self.total_lines:]
            self.last_data = "\n".join(lines)
            
        return self.last_data

    @staticmethod
    def find_start_position(io: BufferedReader, tail=100) -> int:
        io.seek(0, 2)
        file_size = io.tell()
        lines_found = 0
        block_size = 1024
        blocks = []

        while io.tell() > 0 and lines_found <= tail:
            io.seek(max(io.tell() - block_size, 0))
            block = io.read(block_size)
            blocks.append(block)
            lines_found += block.count(b"\n")
            io.seek(-len(block), 1)

        all_read_bytes = b"".join(reversed(blocks))
        lines = all_read_bytes.splitlines()

        if tail >= len(lines):
            return 0
        last_lines = b"\n".join(lines[-tail :])
        return file_size - len(last_lines) - 1

    def load_logfile(self):
        self.stop_reading = True
        self.io = open(self.logfile, "rb")
        self.current_pos = max(self.find_start_position(self.io, self.tail), 0)
        self.stop_reading = False


