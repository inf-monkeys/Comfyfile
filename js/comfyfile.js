import { app } from "../../scripts/app.js";
import { $el, ComfyDialog } from "../../scripts/ui.js";
import { api } from "../../scripts/api.js";

var docStyle = document.createElement("style");
docStyle.innerHTML = `
#cm-comfyfile-dialog {
	width: 600px;
	height: 520px;
	box-sizing: content-box;
	z-index: 10000;
}

.cb-widget {
	width: 400px;
	height: 25px;
	box-sizing: border-box;
	z-index: 10000;
	margin-top: 10px;
	margin-bottom: 5px;
}

.cb-widget-input {
	width: 305px;
	height: 25px;
	box-sizing: border-box;
}
.cb-widget-input:disabled {
	background-color: #444444;
	color: white;
}

.cb-widget-input-label {
	width: 90px;
	height: 25px;
	box-sizing: border-box;
	color: white;
	text-align: right;
	display: inline-block;
	margin-right: 5px;
}

.cm-comfyfile-menu-container {
	column-gap: 20px;
	flex-wrap: wrap;
	box-sizing: content-box;
}

.cm-comfyfile-menu-column {
	display: flex;
	flex-direction: column;
	flex: 1 1 auto;
	width: 300px;
	box-sizing: content-box;
}

.cm-title {
	background-color: black;
	text-align: center;
	height: 40px;
	width: calc(100% - 10px);
	font-weight: bold;
	justify-content: center;
	align-content: center;
	vertical-align: middle;
}

#cm-channel-badge {
	color: white;
	background-color: #AA0000;
	width: 220px;
	height: 23px;
	font-size: 13px;
	border-radius: 5px;
	left: 5px;
	top: 5px;
	align-content: center;
	justify-content: center;
	text-align: center;
	font-weight: bold;
	float: left;
	vertical-align: middle;
	position: relative;
}

#custom-nodes-grid a {
	color: #5555FF;
	font-weight: bold;
	text-decoration: none;
}

#custom-nodes-grid a:hover {
	color: #7777FF;
	text-decoration: underline;
}

#external-models-grid a {
	color: #5555FF;
	font-weight: bold;
	text-decoration: none;
}

#external-models-grid a:hover {
	color: #7777FF;
	text-decoration: underline;
}

#alternatives-grid a {
	color: #5555FF;
	font-weight: bold;
	text-decoration: none;
}

#alternatives-grid a:hover {
	color: #7777FF;
	text-decoration: underline;
}

.cm-notice-board {
	width: 290px;
	height: 270px;
	overflow: auto;
	color: var(--input-text);
	border: 1px solid var(--descrip-text);
	padding: 5px 10px;
	overflow-x: hidden;
	box-sizing: content-box;
}

.cm-notice-board > ul {
	display: block;
	list-style-type: disc;
	margin-block-start: 1em;
	margin-block-end: 1em;
	margin-inline-start: 0px;
	margin-inline-end: 0px;
	padding-inline-start: 40px;
}

.cm-conflicted-nodes-text {
	background-color: #CCCC55 !important;
	color: #AA3333 !important;
	font-size: 10px;
	border-radius: 5px;
	padding: 10px;
}

.cm-warn-note {
	background-color: #101010 !important;
	color: #FF3800 !important;
	font-size: 13px;
	border-radius: 5px;
	padding: 10px;
	overflow-x: hidden;
	overflow: auto;
}

.cm-info-note {
	background-color: #101010 !important;
	color: #FF3800 !important;
	font-size: 13px;
	border-radius: 5px;
	padding: 10px;
	overflow-x: hidden;
	overflow: auto;
}

.comfyfile-form-item {
    display: flex;
    margin: 10px 0;
    justify-content: left;
    align-items: center;
}

.comfyfile-form-input {
    flex-grow: 1
}

.comfyfile-form-label {
    width: 200px
}
`;

document.head.appendChild(docStyle);

export var comfyfile_s3_instance = null;
export var comfyfile_explorer_instance = null;

export function setS3ConfigInstance(obj) {
  comfyfile_s3_instance = obj;
}

export function setComfyfileExplorerInstance(obj) {
  comfyfile_explorer_instance = obj;
}

function jsonToFile(jsonObject, fileName) {
  // 将 JSON 对象转换为字符串
  const jsonString = JSON.stringify(jsonObject);

  // 创建一个 Blob 对象，类型为 'application/json'
  const blob = new Blob([jsonString], { type: "application/json" });

  // 创建一个 File 对象
  const file = new File([blob], fileName, { type: "application/json" });

  return file;
}

function show_message(msg) {
  app.ui.dialog.show(msg);
  app.ui.dialog.element.style.zIndex = 10010;
}

// -----------
class S3ConfigMenuDialog extends ComfyDialog {
  createS3Config() {
    let self = this;
    const descEle = $el(
      "p",
      "When config s3 storage, images and videos of your workflow created will be uploaded to s3 automaticly."
    );
    const enable_s3_storage = $el(
      "input",
      { type: "checkbox", id: "enableS3Storage" },
      []
    );
    const enable_s3_storage_text = $el("label", { for: "enableS3Storage" }, [
      "Enable S3 Storage",
    ]);
    enable_s3_storage_text.style.color = "var(--fg-color)";
    enable_s3_storage_text.style.cursor = "pointer";
    enable_s3_storage.checked = false;

    const accessKeyIdInput = $el(
      "input.comfyfile-form-input",
      { type: "password", id: "accessKeyId" },
      []
    );
    const accessKeyIdInputText = $el(
      "label.comfyfile-form-label",
      { for: "accessKeyId" },
      ["Access Key ID"]
    );
    accessKeyIdInputText.style.color = "var(--fg-color)";
    accessKeyIdInputText.style.cursor = "pointer";

    const accessSecretKeyInput = $el(
      "input.comfyfile-form-input",
      { type: "password", id: "accessSecretKey" },
      []
    );
    const accessSecretKeyInputText = $el(
      "label.comfyfile-form-label",
      { for: "accessSecretKey" },
      ["Access Secret Key"]
    );
    accessSecretKeyInputText.style.color = "var(--fg-color)";
    accessSecretKeyInputText.style.cursor = "pointer";

    const regionInput = $el("input.comfyfile-form-input", { id: "region" }, []);
    const regionInputText = $el(
      "label.comfyfile-form-label",
      { for: "region" },
      ["Region"]
    );
    regionInputText.style.color = "var(--fg-color)";
    regionInputText.style.cursor = "pointer";

    const endpointInput = $el(
      "input.comfyfile-form-input",
      { id: "endpoint" },
      []
    );
    const endpointInputText = $el(
      "label.comfyfile-form-label",
      { for: "endpoint" },
      ["Endpoint Url"]
    );
    endpointInputText.style.color = "var(--fg-color)";
    endpointInputText.style.cursor = "pointer";

    const bucketInput = $el("input.comfyfile-form-input", { id: "bucket" }, []);
    const bucketInputText = $el(
      "label.comfyfile-form-label",
      { for: "bucket" },
      ["Bucket"]
    );
    bucketInputText.style.color = "var(--fg-color)";
    bucketInputText.style.cursor = "pointer";

    const addressingStyleSelect = $el(
      "select.comfyfile-form-input",
      { id: "addressing_style" },
      []
    );
    addressingStyleSelect.appendChild(
      $el("option", { value: "auto", text: "auto" }, [])
    );
    addressingStyleSelect.appendChild(
      $el("option", { value: "path", text: "path" }, [])
    );
    addressingStyleSelect.appendChild(
      $el("option", { value: "virtual", text: "virtual" }, [])
    );
    const addressingStyleSelectText = $el(
      "label.comfyfile-form-label",
      { for: "addressing_style" },
      ["Addressing Style"]
    );
    addressingStyleSelectText.style.color = "var(--fg-color)";
    addressingStyleSelectText.style.cursor = "pointer";

    const publicAccessUrlInput = $el(
      "input.comfyfile-form-input",
      { id: "public_access_url" },
      []
    );
    const publicAccessUrlText = $el(
      "label.comfyfile-form-label",
      { for: "public_access_url" },
      ["Public Access Url"]
    );
    publicAccessUrlText.style.color = "var(--fg-color)";
    publicAccessUrlText.style.cursor = "pointer";

    const form = $el("form", { id: "#myForm" });

    const subMitButton = $el("button", {
      type: "submit",
      textContent: "Submit",
    });
    subMitButton.style.marginRight = "10px";
    const testConnectionButton = $el("button", {
      type: "submit",
      textContent: "Test Connection",
    });

    const getFormData = () => {
      return {
        enabled: enable_s3_storage.checked || false,
        aws_access_key_id: accessKeyIdInput.value || "",
        aws_secret_access_key: accessSecretKeyInput.value || "",
        endpoint_url: endpointInput.value || "",
        region_name: regionInput.value || "",
        bucket: bucketInput.value || "",
        addressing_style: addressingStyleSelect.value || "",
        public_access_url: publicAccessUrlInput.value || "",
      };
    };

    subMitButton.onclick = (event) => {
      event.preventDefault();
      const formData = getFormData();
      // 这里可以将formData发送到服务器端进行进一步处理
      if (formData.enabled) {
      } else {
        if (
          !formData.aws_access_key_id ||
          !formData.aws_secret_access_key ||
          !formData.endpoint_url ||
          !formData.region_name ||
          !formData.bucket ||
          !publicAccessUrlInput.value
        ) {
          return alert("Please fill in forms");
        }
      }
      const requestOptions = {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      };
      api
        .fetchApi(`/comfyfile/save-s3-config`, requestOptions)
        .then((response) => response.json())
        .then((data) => {
          const { success, errMsg } = data;
          if (!success) {
            alert("Test Connection failed: " + errMsg);
          } else {
            alert("Saved!");
          }
        })
        .catch(() => alert("something went wrong"));
    };

    testConnectionButton.onclick = (event) => {
      event.preventDefault();
      const formData = getFormData();
      if (
        !formData.aws_access_key_id ||
        !formData.aws_secret_access_key ||
        !formData.endpoint_url ||
        !formData.region_name ||
        !formData.bucket ||
        !formData.public_access_url
      ) {
        return alert("Please fill in forms");
      }
      const requestOptions = {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      };
      api
        .fetchApi(`/comfyfile/test-s3`, requestOptions)
        .then((response) => response.json())
        .then((data) => {
          const { success, errMsg } = data;
          if (!success) {
            alert("Test Connection failed: " + errMsg);
          } else {
            alert("Everything is ok!");
          }
        })
        .catch(() => alert("something went wrong"));
    };

    form.append(
      ...[
        $el("div.comfyfile-form-item", {}, [descEle]),
        $el("div.comfyfile-form-item", {}, [
          enable_s3_storage,
          enable_s3_storage_text,
        ]),
        $el("div.comfyfile-form-item", {}, [endpointInputText, endpointInput]),
        $el("div.comfyfile-form-item", {}, [regionInputText, regionInput]),
        $el("div.comfyfile-form-item", {}, [
          accessKeyIdInputText,
          accessKeyIdInput,
        ]),
        $el("div.comfyfile-form-item", {}, [
          accessSecretKeyInputText,
          accessSecretKeyInput,
        ]),
        $el("div.comfyfile-form-item", {}, [bucketInputText, bucketInput]),
        $el("div.comfyfile-form-item", {}, [
          addressingStyleSelectText,
          addressingStyleSelect,
        ]),
        $el("div.comfyfile-form-item", {}, [
          publicAccessUrlText,
          publicAccessUrlInput,
        ]),
        subMitButton,
        testConnectionButton,
      ]
    );

    api
      .fetchApi("/comfyfile/get-s3-config")
      .then((response) => response.json())
      .then((response) => {
        const { success, data } = response;
        if (success) {
          enable_s3_storage.checked = data.enabled;
          endpointInput.value = data.endpoint_url;
          regionInput.value = data.region_name;
          accessKeyIdInput.value = data.aws_access_key_id;
          accessSecretKeyInput.value = data.aws_secret_access_key;
          bucketInput.value = data.bucket;
          addressingStyleSelect.value = data.addressing_style;
          publicAccessUrlInput.value = data.public_access_url;
        }
      });

    return [$el("div", {}, [form]), $el("br", {}, [])];
  }

  constructor() {
    super();

    const close_button = $el("button", {
      id: "cm-close-button",
      type: "button",
      textContent: "Close",
      onclick: () => this.close(),
    });

    const content = $el("div.comfy-modal-content", [
      $el("tr.cm-title", {}, [
        $el("font", { size: 6, color: "white" }, [`S3 Configuration Menu`]),
      ]),
      $el("br", {}, []),
      $el("div.cm-comfyfile-menu-container", [...this.createS3Config()]),

      $el("br", {}, []),
      close_button,
    ]);

    content.style.width = "100%";
    content.style.height = "100%";

    this.element = $el(
      "div.comfy-modal",
      { id: "cm-comfyfile-dialog", parent: document.body },
      [content]
    );
  }

  show() {
    this.element.style.display = "block";
  }
}

async function install_remote_comfyfile_app(url) {
  if (comfyfile_explorer_instance) {
    comfyfile_explorer_instance.startInstall(target);
    try {
      const response = await api.fetchApi("/comfyfile/apps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comfyfile_repo: url,
        }),
      });
      const data = await response.json();
      var { success, errMsg } = data;
      if (!success) {
        show_message(`Install failed: ${errMsg}`);
        return false;
      }
      return true;
    } catch (exception) {
      show_message(`Install failed: ${target.title} / ${exception}`);
      return false;
    } finally {
      await comfyfile_explorer_instance.invalidateControl();
      comfyfile_explorer_instance.updateMessage(
        "<BR>To apply the installed apps, please click the 'Refresh' button on the main menu."
      );
    }
  }
}

async function install_local_comfyfile_app(file) {
  if (comfyfile_explorer_instance) {
    comfyfile_explorer_instance.startInstall(file);
    try {
      const response = await api.fetchApi("/comfyfile/apps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          local_comfyfile_repo: file,
        }),
      });
      const data = await response.json();
      var { success, errMsg } = data;
      if (!success) {
        const message = "Install failed.";
        show_message(message);
        return false;
      }
      comfyfile_explorer_instance.updateMessage(
        "<BR>To apply the installed apps, please click the 'Refresh' button on the main menu."
      );
      return true;
    } catch (exception) {
      show_message(`Install failed: ${file} / ${exception}`);
      return false;
    } finally {
      await comfyfile_explorer_instance.invalidateControl();
    }
  }
}

async function getAppList() {
  const response = await api.fetchApi(`/comfyfile/apps`);
  const data = await response.json();
  return data;
}

export class ComfyfileExplorerMenuDislog extends ComfyDialog {
  static instance = null;

  install_buttons = [];
  message_box = null;
  data = null;

  clear() {
    this.install_buttons = [];
    this.message_box = null;
    this.data = null;
  }

  constructor(app, manager_dialog) {
    super();
    this.manager_dialog = manager_dialog;
    this.comfyfile_repo = "";
    this.element = $el("div.comfy-modal", { parent: document.body }, []);
  }

  createControls() {
    return [
      $el("button.cm-small-button", {
        type: "button",
        textContent: "Close",
        onclick: () => {
          this.close();
        },
      }),
    ];
  }

  startInstall(local_comfyfile_repo) {
    comfyfile_explorer_instance.updateMessage(
      `<BR><font color="green">Installing '${local_comfyfile_repo}'</font>`
    );

    for (let i in this.install_buttons) {
      this.install_buttons[i].disabled = true;
      this.install_buttons[i].style.backgroundColor = "gray";
    }
  }

  async install_comfyfile() {
    let comfyfile_repo_url = this.comfyfile_input_box.value.toLowerCase();
    console.log("comfyfile_repo_url: ", comfyfile_repo_url);
    if (comfyfile_repo_url) {
      await install_remote_comfyfile_app(comfyfile_repo_url);
    }
  }

  async install_local_comfyfile(local_comfyfile_repo) {
    if (local_comfyfile_repo) {
      this.startInstall(local_comfyfile_repo);
      await install_local_comfyfile_app(local_comfyfile_repo);
    }
  }

  async invalidateControl() {
    this.clear();
    this.data = (await getAppList()).list;

    while (this.element.children.length) {
      this.element.removeChild(this.element.children[0]);
    }

    this.createHeaderControls();

    if (this.comfyfile_repo) {
      this.comfyfile_input_box.value = this.comfyfile_repo;
    }

    await this.createGrid();
    await this.createBottomControls();
  }

  updateMessage(msg, btn_id) {
    this.message_box.innerHTML = msg;
    if (btn_id) {
      const rebootButton = document.getElementById(btn_id);
      const self = this;
      rebootButton.addEventListener("click", function () {
        if (rebootAPI()) {
          self.close();
          self.manager_dialog.close();
        }
      });
    }
  }

  async createGrid() {
    let self = this;
    var grid = document.createElement("table");
    grid.setAttribute("id", "external-models-grid");

    var thead = document.createElement("thead");
    var tbody = document.createElement("tbody");

    var headerRow = document.createElement("tr");
    thead.style.position = "sticky";
    thead.style.top = "0px";
    thead.style.borderCollapse = "collapse";
    thead.style.tableLayout = "fixed";

    var header1 = document.createElement("th");
    header1.innerHTML = "&nbsp;&nbsp;App NAME&nbsp;&nbsp;";
    header1.style.width = "200px";
    var header2 = document.createElement("th");
    header2.innerHTML = "Display Name";
    header2.style.width = "200px";
    var header3 = document.createElement("th");
    header3.innerHTML = "Description";
    header3.style.width = "200px";
    var header4 = document.createElement("th");
    header4.innerHTML = "Homepage";
    header4.style.width = "30%";
    var header_actions = document.createElement("th");
    header_actions.innerHTML = "Actions";
    header_actions.style.width = "50px";

    thead.appendChild(headerRow);
    headerRow.appendChild(header1);
    headerRow.appendChild(header2);
    headerRow.appendChild(header3);
    headerRow.appendChild(header4);
    headerRow.appendChild(header_actions);

    headerRow.style.backgroundColor = "Black";
    headerRow.style.color = "White";
    headerRow.style.textAlign = "center";
    headerRow.style.width = "100%";
    headerRow.style.padding = "0";

    grid.appendChild(thead);
    grid.appendChild(tbody);

    this.grid_rows = {};

    if (this.data)
      for (var i = 0; i < this.data.length; i++) {
        const data = this.data[i];
        var dataRow = document.createElement("tr");
        var data1 = document.createElement("td");
        data1.style.textAlign = "center";
        data1.innerHTML = data.appName;
        var data2 = document.createElement("td");
        data2.innerHTML = `&nbsp;${data.displayName}`;
        var data3 = document.createElement("td");
        data3.innerHTML = `&nbsp;${data.description}`;
        var data4 = document.createElement("td");
        data4.className = "cm-node-name";
        data4.innerHTML = `&nbsp;<a href=${data.homepage} target="_blank"><font color="skyblue"><b>${data.homepage}</b></font></a>`;
        var data_actions = document.createElement("td");
        var loadBtn = document.createElement("button");
        data_actions.style.textAlign = "center";

        loadBtn.innerHTML = "Load";
        loadBtn.style.backgroundColor = "black";
        loadBtn.style.color = "white";
        loadBtn.style.width = "100px";

        loadBtn.addEventListener("click", function () {
          app.handleFile(jsonToFile(data.workflow));
        });
        data_actions.appendChild(loadBtn);
        var installBtn = document.createElement("button");
        installBtn.style.textAlign = "center";

        installBtn.innerHTML = data.installed ? "Installed" : "Install";
        installBtn.style.backgroundColor = "black";
        installBtn.style.color = "white";
        installBtn.style.width = "100px";
        if (data.installed) {
          installBtn.disabled = true;
          installBtn.style.backgroundColor = "gray";
        } else {
          installBtn.addEventListener("click", function () {
            self.install_local_comfyfile(data.folder);
          });
        }
        this.install_buttons.push(installBtn);

        data_actions.appendChild(installBtn);

        dataRow.style.backgroundColor = "var(--bg-color)";
        dataRow.style.color = "var(--fg-color)";
        dataRow.style.textAlign = "left";

        dataRow.appendChild(data1);
        dataRow.appendChild(data2);
        dataRow.appendChild(data3);
        dataRow.appendChild(data4);
        dataRow.appendChild(data_actions);
        tbody.appendChild(dataRow);

        this.grid_rows[i] = { data: data, control: dataRow };
      }

    const panel = document.createElement("div");
    panel.style.width = "100%";
    panel.appendChild(grid);

    function handleResize() {
      const parentHeight = self.element.clientHeight;
      const gridHeight = parentHeight - 200;

      grid.style.height = gridHeight + "px";
    }
    window.addEventListener("resize", handleResize);

    grid.style.position = "relative";
    grid.style.display = "inline-block";
    grid.style.width = "100%";
    grid.style.height = "100%";
    grid.style.overflowY = "scroll";
    this.element.style.height = "85%";
    this.element.style.width = "80%";
    this.element.appendChild(panel);

    handleResize();
  }

  createHeaderControls() {
    let self = this;
    this.comfyfile_input_box = $el(
      "input.cm-search-filter",
      {
        type: "text",
        id: "comfyfile-input-box",
        placeholder: "Input comfyfile repo url",
        value: this.comfyfile_repo,
      },
      []
    );
    this.comfyfile_input_box.style.width = "300px";
    this.comfyfile_input_box.onkeydown = (event) => {
      if (event.key === "Enter") {
        self.comfyfile_repo = self.comfyfile_input_box.value;
        self.install_comfyfile();
      }
    };

    let install_button = document.createElement("button");
    install_button.className = "cm-small-button";
    install_button.innerHTML = "Installl";
    install_button.onclick = () => {
      self.comfyfile_repo = self.comfyfile_input_box.value;
      self.install_comfyfile();
    };
    install_button.style.display = "inline-block";
    let cell = $el("td", { width: "100%" }, [
      this.comfyfile_input_box,
      "  ",
      install_button,
    ]);
    let search_control = $el("table", { width: "100%" }, [
      $el("tr", {}, [cell]),
    ]);

    cell.style.textAlign = "right";
    this.element.appendChild(search_control);
  }

  async createBottomControls() {
    var close_button = document.createElement("button");
    close_button.className = "cm-small-button";
    close_button.innerHTML = "Close";
    close_button.onclick = () => {
      this.close();
    };
    close_button.style.display = "inline-block";

    this.message_box = $el("div", { id: "custom-download-message" }, [
      $el("br"),
      "",
    ]);
    this.message_box.style.height = "60px";
    this.message_box.style.verticalAlign = "middle";

    this.element.appendChild(this.message_box);
    this.element.appendChild(close_button);
  }

  async show() {
    try {
      this.invalidateControl();
      this.element.style.display = "block";
      this.element.style.zIndex = 10001;
    } catch (exception) {
      app.ui.dialog.show(`Failed to get external model list. / ${exception}`);
    }
  }
}

app.registerExtension({
  name: "Comfy.ComfyfileMenu",
  init() {},

  async setupS3Config(menu) {
    const container = document.createElement("div");
    container.style.display = "flex"; // 设置 div 为 Flex 布局
    container.style.width = "100%";
    container.style.borderRadius = "10";
    container.style.marginBottom = "10px";

    const button = document.createElement("button");
    button.textContent = "Upload to S3";
    container.onclick = () => {
      if (!comfyfile_s3_instance) setS3ConfigInstance(new S3ConfigMenuDialog());
      comfyfile_s3_instance.show();
    };
    button.style.background = "var(--bg-color)";
    button.style.color = "var(--input-text)";
    button.style.border = "none";
    button.style.outline = "none";
    button.style.flexGrow = 10;

    container.appendChild(button);
    container.addEventListener("mouseenter", () => {
      container.style.cursor = "pointer"; // 鼠标悬停时鼠标样式变为手型
    });

    container.addEventListener("mouseleave", () => {
      container.style.cursor = "default"; // 鼠标移出时恢复默认鼠标样式
    });

    button.addEventListener("mouseenter", () => {
      button.style.cursor = "pointer"; // 鼠标悬停时鼠标样式变为手型
    });

    button.addEventListener("mouseleave", () => {
      button.style.cursor = "default"; // 鼠标移出时恢复默认鼠标样式
    });

    menu.append(container);
  },

  async setupComfyfileExplorer(menu) {
    const container = document.createElement("div");
    container.style.background =
      "linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%)";
    container.style.display = "flex"; // 设置 div 为 Flex 布局
    container.style.width = "100%";
    container.style.borderRadius = "10";

    const button = document.createElement("button");
    button.textContent = "Comfyfile";
    container.onclick = () => {
      if (!comfyfile_explorer_instance)
        setComfyfileExplorerInstance(new ComfyfileExplorerMenuDislog());
      comfyfile_explorer_instance.show();
    };
    button.style.color = "black";
    button.style.border = "none";
    button.style.outline = "none";
    button.style.background =
      "linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%)";
    button.style.flexGrow = 10;

    container.appendChild(button);
    container.addEventListener("mouseenter", () => {
      container.style.cursor = "pointer"; // 鼠标悬停时鼠标样式变为手型
    });

    container.addEventListener("mouseleave", () => {
      container.style.cursor = "default"; // 鼠标移出时恢复默认鼠标样式
    });

    button.addEventListener("mouseenter", () => {
      button.style.cursor = "pointer"; // 鼠标悬停时鼠标样式变为手型
    });

    button.addEventListener("mouseleave", () => {
      button.style.cursor = "default"; // 鼠标移出时恢复默认鼠标样式
    });

    menu.append(container);
  },

  async setup() {
    const menu = document.querySelector(".comfy-menu");

    const separator = document.createElement("hr");
    separator.style.margin = "20px 0";
    separator.style.width = "100%";
    menu.append(separator);

    this.setupS3Config(menu);
    this.setupComfyfileExplorer(menu);
  },
});
