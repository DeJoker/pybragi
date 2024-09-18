
class ComfyGraph:
    def __init__(self,
                 graph: dict,
                #  prompt_node: str,
                 img_node: str,
                 save_image_node: str,
                 sampler_nodes: list[str] = [],
                 img_nodes: list[str] = [],
                 ):
        self.graph = graph
        self.img_node = img_node
        self.save_image_node = save_image_node
        self.sampler_nodes = sampler_nodes
        self.img_nodes = img_nodes

        self.set_infer_node('/aigc-nas01/cyj/ComfyUI/output/2376336543.png', 
                            "clay_style/image_test"
                        )
        
    def set_img(self, img_name):
        for node in self.img_nodes:
            self.graph[node]['inputs']["image"] = img_name

    def set_sampler(self, prompt, negative_prompt=None):
        for node in self.sampler_nodes:
            prompt_node = self.graph[node]['inputs']['positive'][0]
            self.graph[prompt_node]['inputs']['text'] = prompt
            if negative_prompt:
                negative_prompt_node = self.graph[node]['inputs']['negative'][0]
                self.graph[negative_prompt_node]['inputs']['text'] = negative_prompt

    def set_infer_node(self, img_path, out_path):
        self.graph[self.img_node]['inputs']["image"] = img_path
        self.graph[self.save_image_node]['inputs']["filename_prefix"] = out_path