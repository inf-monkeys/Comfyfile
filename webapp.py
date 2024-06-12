import streamlit as st
import requests
import socket
import time

comfyui_port = 8188

workflows = []

# 模拟一个获取工作流列表的接口
def get_workflows():
    global workflows
    # 这里应该调用真实的API获取工作流列表
    response = requests.get(f"http://127.0.0.1:{comfyui_port}/comfyfile/apps")
    data = response.json()["list"]
    workflows = data
    return data


# 模拟一个获取工作流详细信息的接口
def get_workflow_details(workflow_folder):
    workflow = [
        workflow for workflow in workflows if workflow["folder"] == workflow_folder
    ][0]
    return workflow["restEndpoint"]["parameters"]


# 模拟一个执行工作流的接口
def execute_workflow(folder, params):
    # 这里应该调用真实的API执行工作流
    response = requests.post(
        f"http://127.0.0.1:{comfyui_port}/comfyfile/run",
        json={"app_name": folder, "input_data": params},
    )
    return response.json()


def install_workflow(folder):
    response = requests.post(
        f"http://127.0.0.1:{comfyui_port}/comfyfile/apps",
        json={"local_comfyfile_repo": folder},
    )
    return response.json()


def wait_comfyui_startup():
    ip = "127.0.0.1"
    timeout = 1
    while True:
        try:
            with socket.create_connection((ip, comfyui_port), timeout=timeout):
                print(f"Port {comfyui_port} on {ip} is now available!")
                break
        except (socket.timeout, ConnectionRefusedError):
            print(
                f"Port {comfyui_port} on {ip} is not available yet. Retrying in {timeout} seconds..."
            )
            time.sleep(timeout)


wait_comfyui_startup()

# 初始化会话状态变量
if 'executing' not in st.session_state:
    st.session_state.executing = False

if 'installing' not in st.session_state:
    st.session_state.installing = False

# Streamlit 应用
st.set_page_config(layout="wide")  # 设置页面为宽布局
st.title("Comfyfile")

# 添加自定义CSS样式
st.markdown(
    """
    [Comfyfile](https://github.com/inf-monkeys/Comfyfile), ComfyUI dependency management made easy.
    """,
    unsafe_allow_html=True,
)

# 页面布局
left_column, _, right_column = st.columns([4, 1, 4])

with left_column:
    st.markdown('<div class="left-col">', unsafe_allow_html=True)
    st.header("Run workflow")

    # 获取工作流列表
    workflows = get_workflows()

    # 选择工作流
    workflow_folder_names = [workflow["folder"] for workflow in workflows]

    def get_display_name_by_folder(folder_name):
        for workflow in workflows:
            if workflow["folder"] == folder_name:
                return workflow["displayName"]
        return folder_name

    def is_workflow_installed(folder_name):
        for workflow in workflows:
            if workflow["folder"] == folder_name:
                installed = workflow["installed"]
                return installed
        return True

    selected_workflow_folder = st.selectbox(
        "Choose a workflow to run",
        workflow_folder_names,
        placeholder="Choose a workflow to run",
        format_func=get_display_name_by_folder,
    )

    # 根据选择的工作流显示相应的输入框
    workflow_input = get_workflow_details(selected_workflow_folder)
    params = {}
    for input_item in workflow_input:
        # input_item 的 type 共有以下几种：string, number, boolean, file, options
        if input_item["type"] == "options":
            options = input_item["options"]
            selected_option = st.selectbox(input_item["displayName"], options)
            params[input_item["name"]] = selected_option
        elif input_item["type"] == "number":
            params[input_item["name"]] = st.number_input(
                input_item["displayName"], input_item["default"]
            )
        elif input_item["type"] == "boolean":
            params[input_item["name"]] = st.checkbox(
                input_item["displayName"], input_item["default"]
            )
        elif input_item["type"] == "file":
            params[input_item["name"]] = st.file_uploader(input_item["displayName"])
        elif input_item["type"] == "string":
            params[input_item["name"]] = st.text_area(
                input_item["displayName"], input_item["default"]
            )
        else:
            st.write(f"Unknown input type: {input_item['type']}")

    workflow_installed = is_workflow_installed(selected_workflow_folder)

    if not workflow_installed:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.error("This workflow is not installed. Please install it first.")
        with col2:
            if st.button("Install", disabled=st.session_state.installing):
                st.session_state.installing = True
                with st.spinner('Installing workflow'):
                    install_workflow(selected_workflow_folder)
                st.session_state.installing = False
                st.experimental_rerun()

    # 执行按钮
    if st.button("Execute", disabled=not workflow_installed or st.session_state.executing):
        st.session_state.executing = True
        with st.spinner('Executing workflow'):
            workflow_execution_result = execute_workflow(selected_workflow_folder, params)
        st.session_state.executing = False

    # API 调用按钮
    if st.button("API"):
        curl_command = f'curl -X POST http://loalhost:{comfyui_port}/comfyfile/run -d \'{{"app_name": "{selected_workflow_folder}", "params": {params}}}\''
        st.code(curl_command, language="bash")
    st.markdown("</div>", unsafe_allow_html=True)

with right_column:
    st.markdown('<div class="right-col">', unsafe_allow_html=True)
    st.header("Workflow output")
    st.write("Here will show workflow execution results when workflow finished.")

    if "workflow_execution_result" in locals():
        st.write(workflow_execution_result)
    st.markdown("</div>", unsafe_allow_html=True)
