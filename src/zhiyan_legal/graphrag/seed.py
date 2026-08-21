"""Seed script: 民法債編 — 買賣/租賃/侵權行為 知識圖譜資料

用法：
    python -m zhiyan_legal.graphrag.seed
"""
from __future__ import annotations
import json
from pathlib import Path

from ..graphrag.schema import (
    EntityType, GraphEntity, GraphRelation, RelationType,
)


def build_civil_code_graph() -> dict:
    """建立民法債編初始知識圖譜（買賣/租賃/侵權行為三章）"""
    nodes = []
    edges = []

    # ── 法規層級 ──
    nodes.append({"id": "stat-civil", "label": "民法", "type": "Statute", "metadata": {}})
    nodes.append({"id": "part-obligation", "label": "債編", "type": "Part", "metadata": {"sub": "第二編"}})
    nodes.append({"id": "part-obligation-general", "label": "債編總論", "type": "Part", "metadata": {}})
    nodes.append({"id": "part-obligation-specific", "label": "債編各論", "type": "Part", "metadata": {}})

    edges.append({"source": "stat-civil", "target": "part-obligation", "type": "has_part"})
    edges.append({"source": "part-obligation", "target": "part-obligation-general", "type": "has_part"})
    edges.append({"source": "part-obligation", "target": "part-obligation-specific", "type": "has_part"})

    # ── 第一章：買賣（§345-§397）──
    nodes.append({"id": "ch-sale", "label": "買賣", "type": "Chapter", "metadata": {"articles": "§345-§397"}})
    edges.append({"source": "part-obligation-specific", "target": "ch-sale", "type": "has_part"})

    sale_articles = [
        ("art-345", "§345 買賣之定義", "稱買賣者，謂當事人約定一方移轉財產權於他方，他方支付價金之契約。"),
        ("art-346", "§346 價金之決定", "價金雖未具體約定，而依情形可得而定者，視為定有價金。"),
        ("art-347", "§347 買賣之成立", "本節規定，於買賣契約成立及效力，除另有規定外，準用之。"),
        ("art-348", "§348 物之出賣人義務", "物之出賣人，負交付其物於買受人，並使其取得該物所有權之義務。"),
        ("art-349", "§349 權利瑕疵擔保", "出賣人應擔保第三人就買賣之標的物，對於買受人不得主張任何權利。"),
        ("art-350", "§350 權利瑕疵擔保之免除", "債權或其他權利之出賣人，應擔保其權利確係存在。"),
        ("art-354", "§354 物之瑕疵擔保", "物之出賣人，對於買受人應擔保其物依民法第三百七十三條之規定危險移轉於買受人時，無滅失或減少其價值之瑕疵。"),
        ("art-355", "§355 瑕疵擔保責任之免除", "買受人於契約成立時，知其物有瑕疵者，出賣人不負擔保之責。"),
        ("art-356", "§356 買受人之檢查通知義務", "買受人應按物之性質，依通常程序從速檢查其所受領之物。"),
        ("art-359", "§359 瑕疵擔保之效力", "買賣因物有瑕疵，而出賣人依前五條之規定，應負擔保之責者，買受人得解除其契約或請求減少其價金。"),
        ("art-360", "§360 瑕疵擔保之請求損害賠償", "買賣之物，缺少出賣人所保證之品質者，買受人得不解除契約或請求減少價金，而請求不履行之損害賠償。"),
        ("art-364", "§364 種類買賣之瑕疵擔保", "買賣之物，僅指定種類者，其物有瑕疵時，買受人得請求另行交付無瑕疵之物。"),
        ("art-365", "§365 瑕疵擔保請求權之除斥期間", "買受人因物有瑕疵，而得解除契約或請求減少價金者，其解除權或請求權，於買受人依第三百五十六條規定為通知後六個月間不行使或自物之交付時起經過五年而消滅。"),
        ("art-367", "§367 買受人之義務", "買受人對於出賣人，有交付約定價金及受領標的物之義務。"),
        ("art-373", "§373 危險負擔", "買賣標的物之利益及危險，自交付時起，均由買受人承受負擔。"),
    ]
    for nid, label, _ in sale_articles:
        nodes.append({"id": nid, "label": label, "type": "Article", "metadata": {"text": _}})
        edges.append({"source": "ch-sale", "target": nid, "type": "has_part"})

    # 買賣章內引用關係
    edges.append({"source": "art-354", "target": "art-347", "type": "references"})
    edges.append({"source": "art-359", "target": "art-354", "type": "references"})
    edges.append({"source": "art-360", "target": "art-354", "type": "references"})
    edges.append({"source": "art-365", "target": "art-356", "type": "references"})
    edges.append({"source": "art-354", "target": "art-373", "type": "references"})
    edges.append({"source": "art-355", "target": "art-354", "type": "exception_to"})

    # ── 第二章：租賃（§421-§463）──
    nodes.append({"id": "ch-lease", "label": "租賃", "type": "Chapter", "metadata": {"articles": "§421-§463"}})
    edges.append({"source": "part-obligation-specific", "target": "ch-lease", "type": "has_part"})

    lease_articles = [
        ("art-421", "§421 租賃之定義", "稱租賃者，謂當事人約定，一方以物租與他方使用收益，他方支付租金之契約。"),
        ("art-422", "§422 不動產租賃之方式", "不動產之租賃契約，其期限逾一年者，應以字據訂立之。"),
        ("art-423", "§423 出租人之交付義務", "出租人應以合於所約定使用收益之租賃物，交付承租人。"),
        ("art-429", "§429 出租人之修繕義務", "租賃物之修繕，除契約另有訂定或另有習慣外，由出租人負擔。"),
        ("art-430", "§430 修繕義務不履行之效力", "租賃關係存續中，租賃物如有修繕之必要，應由出租人負擔者，承租人得定相當期限，催告出租人修繕。"),
        ("art-431", "§431 有益費用之償還", "承租人就租賃物支出有益費用，因而增加該物之價值者，如出租人知其情事而不為反對之表示，於租賃關係終止時，應償還其費用。"),
        ("art-432", "§432 承租人之保管義務", "承租人應以善良管理人之注意，保管租賃物。"),
        ("art-433", "§433 失火責任", "因承租人之同居人或因承租人允許為租賃物之使用收益之第三人應負責之事由，致租賃物毀損滅失者，承租人負損害賠償責任。"),
        ("art-440", "§440 租金遲延之效力", "承租人租金支付有遲延者，出租人得定相當期限，催告承租人支付租金，如承租人於其期限內不為支付，出租人得終止契約。"),
        ("art-443", "§443 轉租之效力", "承租人非經出租人承諾，不得將租賃物轉租於他人。"),
        ("art-450", "§450 租賃之消滅", "租賃定有期限者，其租賃關係，於期限屆滿時消滅。"),
        ("art-451", "§451 默示更新", "租賃期限屆滿後，承租人仍為租賃物之使用收益，而出租人不即表示反對之意思者，視為以不定期限繼續契約。"),
    ]
    for nid, label, _ in lease_articles:
        nodes.append({"id": nid, "label": label, "type": "Article", "metadata": {"text": _}})
        edges.append({"source": "ch-lease", "target": nid, "type": "has_part"})

    edges.append({"source": "art-430", "target": "art-429", "type": "references"})
    edges.append({"source": "art-440", "target": "art-421", "type": "references"})
    edges.append({"source": "art-451", "target": "art-450", "type": "exception_to"})

    # ── 第三章：侵權行為（§184-§198）──
    nodes.append({"id": "ch-tort", "label": "侵權行為", "type": "Chapter", "metadata": {"articles": "§184-§198"}})
    edges.append({"source": "part-obligation-general", "target": "ch-tort", "type": "has_part"})

    tort_articles = [
        ("art-184", "§184 一般侵權行為", "因故意或過失，不法侵害他人之權利者，負損害賠償責任。故意以背於善良風俗之方法，加損害於他人者亦同。"),
        ("art-185", "§185 共同侵權行為", "數人共同不法侵害他人之權利者，連帶負損害賠償責任。"),
        ("art-186", "§186 公務員侵權責任", "公務員因故意違背對於第三人應執行之職務，致第三人受損害者，負賠償責任。"),
        ("art-187", "§187 法定代理人之責任", "無行為能力人或限制行為能力人，不法侵害他人之權利者，以行為時有識別能力為限，與其法定代理人連帶負損害賠償責任。"),
        ("art-188", "§188 僱用人責任", "受僱人因執行職務，不法侵害他人之權利者，由僱用人與行為人連帶負損害賠償責任。"),
        ("art-189", "§189 定作人責任", "承攬人因執行承攬事項，不法侵害他人之權利者，定作人不負損害賠償責任。"),
        ("art-190", "§190 動物占有人責任", "動物加損害於他人者，由其占有人負損害賠償責任。"),
        ("art-191", "§191 工作物所有人責任", "土地上之建築物或其他工作物所致他人權利之損害，由工作物之所有人負賠償責任。"),
        ("art-191-3", "§191-3 危險事業責任", "經營一定事業或從事其他工作或活動之人，其工作或活動之性質或其使用之工具或方法有生損害於他人之危險者，對他人之損害應負賠償責任。"),
        ("art-192", "§192 侵害生命權之損害賠償", "不法侵害他人致死者，對於支出醫療及增加生活上需要之費用或殯葬費之人，亦應負損害賠償責任。"),
        ("art-193", "§193 侵害身體健康之損害賠償", "不法侵害他人之身體或健康者，對於被害人因此喪失或減少勞動能力或增加生活上之需要時，應負損害賠償責任。"),
        ("art-194", "§194 侵害生命權之慰撫金", "不法侵害他人致死者，被害人之父、母、子、女及配偶，雖非財產上之損害，亦得請求賠償相當之金額。"),
        ("art-195", "§195 侵害人格權之慰撫金", "不法侵害他人之身體、健康、名譽、自由、信用、隱私、貞操，或不法侵害其他人格法益而情節重大者，被害人雖非財產上之損害，亦得請求賠償相當之金額。"),
        ("art-196", "§196 物之毀損賠償", "不法毀損他人之物者，被害人得請求賠償其物因毀損所減少之價額。"),
        ("art-197", "§197 侵權行為請求權之消滅時效", "因侵權行為所生之損害賠償請求權，自請求權人知有損害及賠償義務人時起，二年間不行使而消滅。"),
        ("art-198", "§198 時效完成後之拒絕給付權", "因侵權行為對於被害人取得債權者，被害人對該債權之廢止請求權，雖因時效而消滅，仍得拒絕履行。"),
    ]
    for nid, label, _ in tort_articles:
        nodes.append({"id": nid, "label": label, "type": "Article", "metadata": {"text": _}})
        edges.append({"source": "ch-tort", "target": nid, "type": "has_part"})

    # 侵權行為內部引用
    edges.append({"source": "art-185", "target": "art-184", "type": "references"})
    edges.append({"source": "art-187", "target": "art-184", "type": "references"})
    edges.append({"source": "art-188", "target": "art-184", "type": "references"})
    edges.append({"source": "art-190", "target": "art-184", "type": "references"})
    edges.append({"source": "art-191", "target": "art-184", "type": "references"})
    edges.append({"source": "art-191-3", "target": "art-184", "type": "references"})
    edges.append({"source": "art-197", "target": "art-184", "type": "references"})

    # 競合關係
    edges.append({"source": "art-184", "target": "art-191", "type": "conflicts_with"})
    edges.append({"source": "art-227", "target": "art-354", "type": "supplements"})

    # ── 補充：不完全給付（§227）──
    nodes.append({"id": "art-227", "label": "§227 不完全給付", "type": "Article",
                  "metadata": {"text": "因可歸責於債務人之事由，致為不完全給付者，債權人得依關於給付遲延或給付不能之規定行使其權利。"}})
    nodes.append({"id": "ch-general-performance", "label": "債之效力", "type": "Chapter", "metadata": {}})
    edges.append({"source": "part-obligation-general", "target": "ch-general-performance", "type": "has_part"})
    edges.append({"source": "ch-general-performance", "target": "art-227", "type": "has_part"})

    # ── 法律概念 ──
    concepts = [
        ("con-warranty", "物之瑕疵擔保"),
        ("con-right-warranty", "權利瑕疵擔保"),
        ("con-tort", "侵權行為"),
        ("con-lease", "租賃"),
        ("con-sale", "買賣契約"),
        ("con-imputation", "歸責事由"),
        ("con-limiting", "消滅時效"),
        ("con-damages", "損害賠償"),
    ]
    for cid, clabel in concepts:
        nodes.append({"id": cid, "label": clabel, "type": "Concept", "metadata": {}})

    # 概念與條文連結
    edges.append({"source": "con-warranty", "target": "art-354", "type": "references"})
    edges.append({"source": "con-warranty", "target": "art-359", "type": "references"})
    edges.append({"source": "con-right-warranty", "target": "art-349", "type": "references"})
    edges.append({"source": "con-tort", "target": "art-184", "type": "references"})
    edges.append({"source": "con-tort", "target": "art-185", "type": "references"})
    edges.append({"source": "con-tort", "target": "art-188", "type": "references"})
    edges.append({"source": "con-lease", "target": "art-421", "type": "references"})
    edges.append({"source": "con-sale", "target": "art-345", "type": "references"})
    edges.append({"source": "con-imputation", "target": "art-184", "type": "references"})
    edges.append({"source": "con-limiting", "target": "art-197", "type": "references"})
    edges.append({"source": "con-damages", "target": "art-192", "type": "references"})
    edges.append({"source": "con-damages", "target": "art-193", "type": "references"})
    edges.append({"source": "con-damages", "target": "art-194", "type": "references"})
    edges.append({"source": "con-damages", "target": "art-195", "type": "references"})

    return {"nodes": nodes, "edges": edges}


def main():
    output_dir = Path("data/knowledge_graph")
    output_dir.mkdir(parents=True, exist_ok=True)

    data = build_civil_code_graph()
    output_path = output_dir / "civil_code.json"
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ 知識圖譜已產生：{output_path}")
    print(f"   節點數：{len(data['nodes'])}")
    print(f"   邊數：{len(data['edges'])}")

    # 統計
    from collections import Counter
    type_count = Counter(n["type"] for n in data["nodes"])
    for t, c in type_count.most_common():
        print(f"   {t}: {c}")


if __name__ == "__main__":
    main()
