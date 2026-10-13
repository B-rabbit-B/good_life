import { Button } from '../../components/Button'
import { Sensitive } from '../../components/Sensitive'
import { TextField } from '../../components/TextField'

/** 后端的长度上限（SearchIn.place 50、city 20） */
const PLACE_MAX = 50
const CITY_MAX = 20

/**
 * 地点输入（敏感区 place）：地名或地标、城市（可不填）；有已保存的大致区域时多一个“用已保存的区域”。
 * 区域名也是地点，所以写在同一块敏感区里。
 */
export function PlaceForm({ place, city, onPlace, onCity, savedArea, onUseSaved, busy }: {
  place: string
  city: string
  onPlace: (value: string) => void
  onCity: (value: string) => void
  savedArea: string | null
  onUseSaved: () => void
  busy: boolean
}) {
  return (
    <Sensitive area="place" className="plate rs-place">
      <div className="rs-pair">
        <TextField label="地名或地标" value={place} onChange={onPlace} maxLength={PLACE_MAX} autoComplete="off" />
        <TextField label="城市（可不填）" value={city} onChange={onCity} maxLength={CITY_MAX} autoComplete="off" />
      </div>
      {savedArea !== null && (
        <div className="rs-saved">
          <Button variant="text" icon="pin" isDisabled={busy} onPress={onUseSaved}>用已保存的区域：{savedArea}</Button>
        </div>
      )}
    </Sensitive>
  )
}
