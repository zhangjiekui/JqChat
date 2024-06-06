import AssistantIcon from '@mui/icons-material/Assistant';

import "./Sidebar.css";

export default function Sidebar(props: {
  models: Array<{ name: string; displayName: string }>;
  docs:Array<string>;
  selectedModel: string;
  onSelectModel: any;
  selectedDoc:any;
  onSelectedDoc:any;
  setOpenAIKey: any;
  openAIKey: string;
}) {
  const handleOpenAIButtonClick = () => {
    const key = prompt("请输入您的OpenAI密钥", props.openAIKey);
    if (key != null) {
      props.setOpenAIKey(key);
    }
  };
  return (
    <>
      <div className="sidebar">
        <div className="logo">
            <AssistantIcon /> 医疗卫生知识BOT
        </div>
        <div className="settings">
            <label className="header">设置</label>
            <label>知识库</label>
            <select
            value={props.selectedDoc}
            onChange={(event) => props.onSelectedDoc(event.target.value)}
            >
              <option key="" value="">
                    ---请选择---
                </option>
            {props.docs.map((key,value) => {
                return (
                <option key={key} value={value}>
                    {value}
                </option>
                );
            })}
            </select>
            <label hidden>模型</label>
            <select hidden
            value={props.selectedModel}
            onChange={(event) => props.onSelectModel(event.target.value)}
            >
            {props.models.map((model, index) => {
                return (
                <option key={index} value={model.name}>
                    {model.displayName}
                </option>
                );
            })}
            </select>
            <label  hidden>证书</label>
            <button  hidden onClick={handleOpenAIButtonClick}>设置OpenAI密钥</button>
        </div>
      </div>
    </>
  );
}
