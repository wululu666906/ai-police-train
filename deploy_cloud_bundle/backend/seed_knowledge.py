from services.rag_service import rag_service

def seed():
    print("Seeding legal knowledge...")
    knowledge_base = [
        "《治安管理处罚法》第四十三条：殴打他人的，或者故意伤害他人身体的，处五日以上十日以下拘留，并处二百元以上五百元以下罚款。",
        "《治安管理处罚法》第九条：对于因民间纠纷引起的打架斗殴或者损毁他人财物等违反治安管理行为，情节较轻的，公安机关可以调解处理。",
        "执法话术：面对情绪激动的报警人，应先使用‘请保持冷静，我们正在处理’、‘请配合我们的工作，这不仅是为了解决问题，也是为了您的安全’等话术。",
        "口角纠纷处理原则：应采取‘冷处理’与‘热处理’相结合，先隔离双方，再分别询问事实。",
        "故意伤害认定：如果伤情达到轻伤以上，则触犯《刑法》第二百三十四条，构成故意伤害罪。"
    ]
    
    rag_service.add_documents(knowledge_base)
    print("Seeding complete.")

if __name__ == "__main__":
    seed()
