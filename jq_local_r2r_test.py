def r2r_test():
    print("R2R服务测试--------请首先启动R2R服务--------")
    from r2r import R2RClient
    client = R2RClient(base_url='http://10.1.150.105:7272') # can set remote w/ R2RClient(base_url=...)
    client.users.login("admin@example.com", "change_me_immediately")
    try:
        doc=client.documents.create(file_path="/data/projects/JqChatV2/JqChat/财务发票模板.docx")
        print(doc)
        doc_id=doc.results.document_id
        message = doc.results.message
        print(doc_id)
        print(message)
    except Exception as e:
        print(e)


if __name__ == "__main__":
    # model_test()
    r2r_test()